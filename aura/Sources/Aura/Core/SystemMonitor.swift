import Foundation
import Darwin
import IOKit
import IOKit.ps
import AppKit

struct ProcessInfoRow: Identifiable, Hashable {
    let pid: Int32
    let name: String
    let cpu: Double      // en %
    let memory: Int64    // en octets
    var id: Int32 { pid }
}

struct BatteryInfo {
    var present = false
    var level: Double = 0
    var isCharging = false
    var onAC = false
    var cycleCount: Int?
    var health: Double?          // capacité max / capacité d'origine
    var timeRemaining: Int?      // minutes
    var temperature: Double?     // °C
}

struct Sample: Identifiable {
    let id = UUID()
    let t: Date
    let value: Double
}

@MainActor
final class SystemMonitor: ObservableObject {
    static let shared = SystemMonitor()

    @Published var cpuUsage: Double = 0
    @Published var cpuPerCore: [Double] = []
    @Published var memUsed: Int64 = 0
    @Published var memTotal: Int64 = Int64(ProcessInfo.processInfo.physicalMemory)
    @Published var memWired: Int64 = 0
    @Published var memCompressed: Int64 = 0
    @Published var memApp: Int64 = 0
    @Published var memCached: Int64 = 0
    @Published var swapUsed: Int64 = 0
    @Published var diskTotal: Int64 = 0
    @Published var diskFree: Int64 = 0
    @Published var diskPurgeable: Int64 = 0
    @Published var netIn: Double = 0
    @Published var netOut: Double = 0
    @Published var battery = BatteryInfo()
    @Published var thermal: ProcessInfo.ThermalState = .nominal
    @Published var processes: [ProcessInfoRow] = []
    @Published var uptime: TimeInterval = 0
    @Published var temps = TemperatureSummary()

    @Published var cpuHistory: [Sample] = []
    @Published var memHistory: [Sample] = []
    @Published var netInHistory: [Sample] = []
    @Published var netOutHistory: [Sample] = []

    private var timer: Timer?
    private var prevTicks: [(user: UInt64, sys: UInt64, idle: UInt64, nice: UInt64)] = []
    private var prevNet: (inB: UInt64, outB: UInt64, t: Date)?
    private var tick = 0
    private var slowReadInFlight = false
    private let historyLength = 90

    var memPressure: Double { memTotal > 0 ? Double(memUsed) / Double(memTotal) : 0 }
    var diskUsedRatio: Double { diskTotal > 0 ? Double(diskTotal - diskFree) / Double(diskTotal) : 0 }

    var healthScore: Int {
        var score = 100.0
        score -= max(0, cpuUsage - 0.5) * 40
        score -= max(0, memPressure - 0.7) * 80
        score -= max(0, diskUsedRatio - 0.8) * 150
        if swapUsed > 2_000_000_000 { score -= 8 }
        if thermal == .serious { score -= 15 }
        if thermal == .critical { score -= 30 }
        if let h = temps.cpu, h > 90 { score -= 10 }
        return Int(max(0, min(100, score)))
    }

    func start() {
        guard timer == nil else { return }
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    func stop() { timer?.invalidate(); timer = nil }

    func refresh() {
        tick += 1
        readCPU()
        readMemory()
        readNetwork()
        thermal = ProcessInfo.processInfo.thermalState
        uptime = ProcessInfo.processInfo.systemUptime
        // Mesures lentes (disque, batterie, processus, capteurs) : jamais sur le fil principal
        if tick % 4 == 1 && !slowReadInFlight {
            slowReadInFlight = true
            let withPurgeable = tick % 40 == 1     // l'espace purgeable est très coûteux : rarement
            Task.detached(priority: .utility) {
                let v = FS.volumeInfo(includePurgeable: withPurgeable)
                let b = Self.readBattery()
                let rows = Self.readProcesses()
                let t = Sensors.readTemperatures()
                await MainActor.run {
                    self.diskTotal = v.total
                    self.diskFree = v.free
                    if withPurgeable { self.diskPurgeable = v.purgeable }
                    self.battery = b
                    self.processes = rows
                    self.temps = t
                    self.slowReadInFlight = false
                }
            }
        }
        let now = Date()
        push(&cpuHistory, Sample(t: now, value: cpuUsage * 100))
        push(&memHistory, Sample(t: now, value: memPressure * 100))
        push(&netInHistory, Sample(t: now, value: netIn))
        push(&netOutHistory, Sample(t: now, value: netOut))
    }

    private func push(_ arr: inout [Sample], _ s: Sample) {
        arr.append(s)
        if arr.count > historyLength { arr.removeFirst(arr.count - historyLength) }
    }

    // MARK: CPU

    private func readCPU() {
        var count: natural_t = 0
        var info: processor_info_array_t?
        var infoCount: mach_msg_type_number_t = 0
        guard host_processor_info(mach_host_self(), PROCESSOR_CPU_LOAD_INFO, &count, &info, &infoCount) == KERN_SUCCESS,
              let info else { return }
        defer {
            vm_deallocate(mach_task_self_, vm_address_t(bitPattern: info),
                          vm_size_t(Int(infoCount) * MemoryLayout<integer_t>.stride))
        }
        var ticks: [(UInt64, UInt64, UInt64, UInt64)] = []
        for i in 0..<Int(count) {
            let base = Int(CPU_STATE_MAX) * i
            ticks.append((UInt64(UInt32(bitPattern: info[base + Int(CPU_STATE_USER)])),
                          UInt64(UInt32(bitPattern: info[base + Int(CPU_STATE_SYSTEM)])),
                          UInt64(UInt32(bitPattern: info[base + Int(CPU_STATE_IDLE)])),
                          UInt64(UInt32(bitPattern: info[base + Int(CPU_STATE_NICE)]))))
        }
        if prevTicks.count == ticks.count {
            var cores: [Double] = []
            var busyAll: Double = 0, totalAll: Double = 0
            for (a, b) in zip(prevTicks, ticks) {
                let user = Double(b.0 &- a.user), sys = Double(b.1 &- a.sys)
                let idle = Double(b.2 &- a.idle), nice = Double(b.3 &- a.nice)
                let total = user + sys + idle + nice
                let busy = user + sys + nice
                cores.append(total > 0 ? busy / total : 0)
                busyAll += busy; totalAll += total
            }
            cpuPerCore = cores
            cpuUsage = totalAll > 0 ? busyAll / totalAll : 0
        }
        prevTicks = ticks.map { (user: $0.0, sys: $0.1, idle: $0.2, nice: $0.3) }
    }

    // MARK: Mémoire

    private func readMemory() {
        var stats = vm_statistics64()
        var size = mach_msg_type_number_t(MemoryLayout<vm_statistics64_data_t>.stride / MemoryLayout<integer_t>.stride)
        let result = withUnsafeMutablePointer(to: &stats) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(size)) {
                host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &size)
            }
        }
        guard result == KERN_SUCCESS else { return }
        let page = Int64(vm_kernel_page_size)
        let wired = Int64(stats.wire_count) * page
        let compressed = Int64(stats.compressor_page_count) * page
        let internalPages = Int64(stats.internal_page_count) - Int64(stats.purgeable_count)
        let app = max(0, internalPages) * page
        let cached = (Int64(stats.external_page_count) + Int64(stats.purgeable_count)) * page
        memWired = wired
        memCompressed = compressed
        memApp = app
        memCached = cached
        memUsed = app + wired + compressed

        var swap = xsw_usage()
        var sz = MemoryLayout<xsw_usage>.size
        if sysctlbyname("vm.swapusage", &swap, &sz, nil, 0) == 0 {
            swapUsed = Int64(swap.xsu_used)
        }
    }

    // MARK: Réseau

    private func readNetwork() {
        var inB: UInt64 = 0, outB: UInt64 = 0
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddr) == 0, let first = ifaddr else { return }
        defer { freeifaddrs(ifaddr) }
        var ptr: UnsafeMutablePointer<ifaddrs>? = first
        while let p = ptr {
            let ifa = p.pointee
            if let addr = ifa.ifa_addr, addr.pointee.sa_family == UInt8(AF_LINK),
               let data = ifa.ifa_data {
                let name = String(cString: ifa.ifa_name)
                if !name.hasPrefix("lo") {
                    let d = data.assumingMemoryBound(to: if_data.self).pointee
                    inB += UInt64(d.ifi_ibytes)
                    outB += UInt64(d.ifi_obytes)
                }
            }
            ptr = ifa.ifa_next
        }
        let now = Date()
        if let prev = prevNet {
            let dt = now.timeIntervalSince(prev.t)
            if dt > 0 {
                netIn = inB >= prev.inB ? Double(inB - prev.inB) / dt : 0
                netOut = outB >= prev.outB ? Double(outB - prev.outB) / dt : 0
            }
        }
        prevNet = (inB, outB, now)
    }

    // MARK: Batterie

    nonisolated static func readBattery() -> BatteryInfo {
        var b = BatteryInfo()
        guard let blob = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
              let list = IOPSCopyPowerSourcesList(blob)?.takeRetainedValue() as? [CFTypeRef] else { return b }
        for ps in list {
            guard let d = IOPSGetPowerSourceDescription(blob, ps)?.takeUnretainedValue() as? [String: Any],
                  (d[kIOPSTypeKey] as? String) == kIOPSInternalBatteryType else { continue }
            b.present = true
            let cur = d[kIOPSCurrentCapacityKey] as? Int ?? 0
            let max = d[kIOPSMaxCapacityKey] as? Int ?? 100
            b.level = max > 0 ? Double(cur) / Double(max) : 0
            b.isCharging = d[kIOPSIsChargingKey] as? Bool ?? false
            b.onAC = (d[kIOPSPowerSourceStateKey] as? String) == kIOPSACPowerValue
            if let t = d[kIOPSTimeToEmptyKey] as? Int, t > 0 { b.timeRemaining = t }
        }
        // Détails avancés (cycles, santé, température) via AppleSmartBattery
        let service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSmartBattery"))
        if service != 0 {
            defer { IOObjectRelease(service) }
            func prop(_ k: String) -> Any? {
                IORegistryEntryCreateCFProperty(service, k as CFString, kCFAllocatorDefault, 0)?.takeRetainedValue()
            }
            b.cycleCount = prop("CycleCount") as? Int
            let design = prop("DesignCapacity") as? Int
            let rawMax = (prop("AppleRawMaxCapacity") as? Int) ?? (prop("NominalChargeCapacity") as? Int)
            if let design, let rawMax, design > 0 { b.health = min(1.0, Double(rawMax) / Double(design)) }
            if let t = prop("Temperature") as? Int { b.temperature = Double(t) / 100.0 }
        }
        return b
    }

    // MARK: Processus

    nonisolated static func readProcesses() -> [ProcessInfoRow] {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/ps")
        p.arguments = ["-Aceo", "pid=,pcpu=,rss=,comm="]
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return [] }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        guard let text = String(data: data, encoding: .utf8) else { return [] }
        var rows: [ProcessInfoRow] = []
        for line in text.split(separator: "\n") {
            let parts = line.split(separator: " ", maxSplits: 3, omittingEmptySubsequences: true)
            guard parts.count == 4, let pid = Int32(parts[0]), let cpu = Double(parts[1]),
                  let rss = Int64(parts[2]) else { continue }
            rows.append(ProcessInfoRow(pid: pid, name: String(parts[3]), cpu: cpu, memory: rss * 1024))
        }
        return rows
    }

    // MARK: Actions

    func terminate(_ pid: Int32, force: Bool = false) {
        if let app = NSRunningApplication(processIdentifier: pid) {
            _ = force ? app.forceTerminate() : app.terminate()
        } else {
            kill(pid, force ? SIGKILL : SIGTERM)
        }
    }

    /// Libère la mémoire inactive (commande `purge`, demande le mot de passe admin).
    func purgeMemory() {
        let script = "do shell script \"/usr/sbin/purge\" with administrator privileges"
        var err: NSDictionary?
        NSAppleScript(source: script)?.executeAndReturnError(&err)
        refresh()
    }

    /// Vide le cache DNS (mot de passe admin).
    func flushDNS() {
        let script = "do shell script \"dscacheutil -flushcache; killall -HUP mDNSResponder\" with administrator privileges"
        var err: NSDictionary?
        NSAppleScript(source: script)?.executeAndReturnError(&err)
    }
}
