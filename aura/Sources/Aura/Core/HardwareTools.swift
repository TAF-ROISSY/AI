import Foundation
import AppKit
import IOKit.pwr_mgt

// MARK: - Réseau

struct SpeedTestResult {
    let date: Date
    let download: Double      // bits/s
    let upload: Double        // bits/s
    let latency: Double?      // ms
    let responsiveness: String?
    let interface: String?
}

struct AppNetworkUsage: Identifiable {
    let id = UUID()
    let name: String
    let pid: Int32
    let received: Int64
    let sent: Int64
    var total: Int64 { received + sent }
}

@MainActor
final class NetworkTools: ObservableObject {
    @Published var isTesting = false
    @Published var lastTest: SpeedTestResult?
    @Published var history: [SpeedTestResult] = []
    @Published var usage: [AppNetworkUsage] = []
    @Published var isMeasuring = false
    @Published var wifi: [String: String] = [:]
    @Published var error = ""

    static func mbps(_ bps: Double) -> String { String(format: "%.0f Mb/s", bps / 1_000_000) }

    /// Test de débit avec l'outil intégré d'Apple (`networkQuality`), environ 20 secondes.
    func runSpeedTest() async {
        guard !isTesting else { return }
        isTesting = true
        error = ""
        let r = await Task.detached { Shell.run("/usr/bin/networkQuality", ["-c"], timeout: 90) }.value
        isTesting = false
        guard let start = r.output.firstIndex(of: "{"),
              let j = try? JSONSerialization.jsonObject(with: Data(r.output[start...].utf8)) as? [String: Any] else {
            error = "Test impossible : vérifie ta connexion internet."
            return
        }
        func num(_ k: String) -> Double? { (j[k] as? NSNumber)?.doubleValue }
        let rpm = num("responsiveness")
        let res = SpeedTestResult(date: Date(), download: num("dl_throughput") ?? 0, upload: num("ul_throughput") ?? 0,
                                  latency: num("base_rtt"),
                                  responsiveness: rpm.map { $0 > 1000 ? "Excellente" : $0 > 300 ? "Bonne" : $0 > 100 ? "Moyenne" : "Faible" },
                                  interface: j["interface_name"] as? String)
        lastTest = res
        history.insert(res, at: 0)
        if history.count > 20 { history.removeLast() }
    }

    /// Consommation réseau par application (outil `nettop`, mesure sur 3 secondes).
    func measureUsage() async {
        isMeasuring = true
        let rows = await Task.detached { () -> [AppNetworkUsage] in
            let r = Shell.run("/usr/bin/nettop", ["-P", "-L", "2", "-s", "3", "-x", "-J", "bytes_in,bytes_out"], timeout: 30)
            // Deux relevés : on garde le second (cumul depuis le démarrage des processus)
            let lines = r.output.split(separator: "\n").map(String.init)
            let headerIdx = lines.indices.filter { lines[$0].hasPrefix(",bytes_in") || lines[$0].hasPrefix("time,") }
            let start = (headerIdx.last ?? -1) + 1
            var out: [AppNetworkUsage] = []
            for line in lines[max(0, start)...] {
                let cols = line.split(separator: ",", omittingEmptySubsequences: false).map(String.init)
                guard cols.count >= 3 else { continue }
                let nameCol = cols[cols.count - 3]
                guard let inB = Int64(cols[cols.count - 2]), let outB = Int64(cols[cols.count - 1]), inB + outB > 0 else { continue }
                let parts = nameCol.split(separator: ".")
                let pid = Int32(parts.last ?? "") ?? 0
                let name = parts.dropLast().joined(separator: ".")
                out.append(AppNetworkUsage(name: name.isEmpty ? nameCol : name, pid: pid, received: inB, sent: outB))
            }
            return out.sorted { $0.total > $1.total }
        }.value
        usage = Array(rows.prefix(30))
        isMeasuring = false
    }

    /// Infos Wi-Fi (réseau, signal, débit négocié).
    func readWifi() async {
        wifi = await Task.detached { () -> [String: String] in
            let out = Shell.run("/usr/sbin/system_profiler", ["SPAirPortDataType"], timeout: 30).output
            var info: [String: String] = [:]
            var inCurrent = false
            for raw in out.split(separator: "\n") {
                let l = raw.trimmingCharacters(in: .whitespaces)
                if l.hasPrefix("Current Network Information:") { inCurrent = true; continue }
                if inCurrent && l.hasPrefix("Other Local Wi-Fi Networks:") { break }
                guard inCurrent else { continue }
                if l.hasSuffix(":") && info["Réseau"] == nil {
                    info["Réseau"] = String(l.dropLast())
                    continue
                }
                for (key, label) in [("PHY Mode:", "Norme"), ("Channel:", "Canal"), ("Signal / Noise:", "Signal / bruit"),
                                     ("Transmit Rate:", "Débit négocié"), ("Security:", "Sécurité")] where l.hasPrefix(key) {
                    info[label] = l.dropFirst(key.count).trimmingCharacters(in: .whitespaces)
                }
            }
            return info
        }.value
    }
}

// MARK: - Disques

struct PhysicalDisk: Identifiable {
    let id: String              // disk0, disk4…
    let name: String
    let size: Int64
    let isInternal: Bool
    let isSSD: Bool
    let protocolName: String
    let smart: String           // Verified, Failing, Not Supported…
    let volumes: [VolumeInfo]
    var smartOK: Bool? {
        switch smart.lowercased() {
        case "verified": return true
        case "failing": return false
        default: return nil
        }
    }
}

struct DiskBenchmark {
    let write: Double   // octets/s
    let read: Double
}

@MainActor
final class DiskTools: ObservableObject {
    @Published var disks: [PhysicalDisk] = []
    @Published var isLoading = false
    @Published var benchmarking: String?
    @Published var benchmarks: [String: DiskBenchmark] = [:]
    @Published var message = ""

    nonisolated static func plist(_ args: [String]) -> [String: Any] {
        let r = Shell.run("/usr/sbin/diskutil", args, timeout: 30)
        guard let d = r.output.data(using: .utf8),
              let p = try? PropertyListSerialization.propertyList(from: d, format: nil) as? [String: Any] else { return [:] }
        return p
    }

    func load() async {
        isLoading = true
        let vols = await Task.detached { VolumeManager.readVolumes() }.value
        disks = await Task.detached { () -> [PhysicalDisk] in
            let list = Self.plist(["list", "-plist", "physical"])
            let ids = (list["WholeDisks"] as? [String]) ?? []
            return ids.map { id in
                let info = Self.plist(["info", "-plist", id])
                // Volumes montés appartenant à ce disque (y compris via un conteneur APFS)
                let parts = ((list["AllDisksAndPartitions"] as? [[String: Any]]) ?? [])
                    .first { ($0["DeviceIdentifier"] as? String) == id }
                var stores: [String] = [id]
                for p in (parts?["Partitions"] as? [[String: Any]]) ?? [] {
                    if let pid = p["DeviceIdentifier"] as? String { stores.append(pid) }
                }
                let containers = stores.compactMap { s -> String? in
                    let i = Self.plist(["info", "-plist", s])
                    return i["APFSContainerReference"] as? String
                }
                let mine = vols.filter { v in
                    let i = Self.plist(["info", "-plist", v.url.path])
                    let parent = i["ParentWholeDisk"] as? String ?? ""
                    return parent == id || containers.contains(parent) || stores.contains(i["DeviceIdentifier"] as? String ?? "")
                }
                return PhysicalDisk(id: id,
                                    name: info["MediaName"] as? String ?? id,
                                    size: (info["TotalSize"] as? NSNumber)?.int64Value ?? (info["Size"] as? NSNumber)?.int64Value ?? 0,
                                    isInternal: info["Internal"] as? Bool ?? false,
                                    isSSD: info["SolidState"] as? Bool ?? false,
                                    protocolName: info["BusProtocol"] as? String ?? "—",
                                    smart: info["SMARTStatus"] as? String ?? "Non disponible",
                                    volumes: mine)
            }
        }.value
        isLoading = false
    }

    /// Test de vitesse : écrit puis relit un fichier de 1 Go sans cache, puis le supprime.
    func benchmark(_ volume: VolumeInfo) async {
        guard benchmarking == nil else { return }
        guard !volume.isReadOnly, volume.free > 2_000_000_000 else {
            message = "\(volume.name) : il faut au moins 2 Go libres et un support modifiable."
            return
        }
        benchmarking = volume.id
        message = ""
        let dir = volume.url.path == "/" ? FS.fm.temporaryDirectory : volume.url
        let result = await Task.detached { Self.runBenchmark(in: dir) }.value
        if let result { benchmarks[volume.id] = result } else { message = "Test impossible sur \(volume.name)." }
        benchmarking = nil
    }

    nonisolated static func runBenchmark(in dir: URL) -> DiskBenchmark? {
        let file = dir.appendingPathComponent(".aura-speedtest-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: file) }
        let chunk = 8 << 20                     // 8 Mo
        let total = 1 << 30                     // 1 Go
        var buf = [UInt8](repeating: 0, count: chunk)
        for i in stride(from: 0, to: chunk, by: 4096) { buf[i] = UInt8(truncatingIfNeeded: i) }

        // Écriture
        let wfd = open(file.path, O_CREAT | O_WRONLY | O_TRUNC, 0o600)
        guard wfd >= 0 else { return nil }
        _ = fcntl(wfd, F_NOCACHE, 1)
        var t0 = Date()
        var written = 0
        while written < total {
            let n = buf.withUnsafeBytes { write(wfd, $0.baseAddress, chunk) }
            if n <= 0 { close(wfd); return nil }
            written += n
        }
        fsync(wfd)
        close(wfd)
        let writeSpeed = Double(written) / Date().timeIntervalSince(t0)

        // Lecture
        let rfd = open(file.path, O_RDONLY)
        guard rfd >= 0 else { return nil }
        _ = fcntl(rfd, F_NOCACHE, 1)
        t0 = Date()
        var readTotal = 0
        while true {
            let n = buf.withUnsafeMutableBytes { read(rfd, $0.baseAddress, chunk) }
            if n <= 0 { break }
            readTotal += n
        }
        close(rfd)
        let readSpeed = Double(readTotal) / Date().timeIntervalSince(t0)
        return DiskBenchmark(write: writeSpeed, read: readSpeed)
    }
}

// MARK: - Historique de la batterie

struct BatterySnapshot: Codable, Identifiable {
    var id: Date { date }
    let date: Date
    let health: Double      // 0…1
    let cycles: Int
}

@MainActor
final class BatteryHistory: ObservableObject {
    @Published var snapshots: [BatterySnapshot] = []

    private var fileURL: URL {
        let dir = FS.url("~/Library/Application Support/Aura")
        try? FS.fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("batterie.json")
    }

    init() {
        if let d = try? Data(contentsOf: fileURL),
           let s = try? JSONDecoder().decode([BatterySnapshot].self, from: d) {
            snapshots = s
        }
    }

    /// Enregistre au plus un relevé par jour.
    func record(_ b: BatteryInfo) {
        guard b.present, let h = b.health else { return }
        let today = Calendar.current.startOfDay(for: Date())
        if let last = snapshots.last, Calendar.current.isDate(last.date, inSameDayAs: today) { return }
        snapshots.append(BatterySnapshot(date: Date(), health: h, cycles: b.cycleCount ?? 0))
        if let d = try? JSONEncoder().encode(snapshots) { try? d.write(to: fileURL) }
    }

    /// Perte de capacité par mois (sur la période enregistrée).
    var monthlyLoss: Double? {
        guard let f = snapshots.first, let l = snapshots.last, l.date.timeIntervalSince(f.date) > 20 * 86400 else { return nil }
        let months = l.date.timeIntervalSince(f.date) / (30 * 86400)
        return (f.health - l.health) / months
    }
}

// MARK: - Rester éveillé

@MainActor
final class KeepAwake: ObservableObject {
    @Published var isActive = false
    @Published var until: Date?
    private var assertion: IOPMAssertionID = 0
    private var timer: Timer?

    /// `minutes` nil = jusqu'à désactivation manuelle.
    func activate(minutes: Int?, display: Bool = true) {
        deactivate()
        let type = (display ? kIOPMAssertionTypeNoDisplaySleep : kIOPMAssertionTypeNoIdleSleep) as CFString
        let ok = IOPMAssertionCreateWithName(type, IOPMAssertionLevel(kIOPMAssertionLevelOn),
                                             "Aura : rester éveillé" as CFString, &assertion)
        guard ok == kIOReturnSuccess else { return }
        isActive = true
        if let m = minutes {
            until = Date().addingTimeInterval(Double(m) * 60)
            timer = Timer.scheduledTimer(withTimeInterval: Double(m) * 60, repeats: false) { [weak self] _ in
                Task { @MainActor in self?.deactivate() }
            }
        } else {
            until = nil
        }
    }

    func deactivate() {
        timer?.invalidate()
        timer = nil
        if assertion != 0 { IOPMAssertionRelease(assertion); assertion = 0 }
        isActive = false
        until = nil
    }
}
