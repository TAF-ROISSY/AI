import Foundation
import AppKit
import SwiftUI
import Darwin

/// Relevé brut d'un processus (lu hors du fil principal).
struct ProcSample {
    let pid: pid_t
    let path: String
    let cpuAbs: UInt64          // temps processeur cumulé (unités mach)
    let energyNJ: UInt64        // énergie cumulée (nanojoules)
    let footprint: UInt64       // mémoire réelle (comme le Moniteur d'activité)
    let diskRead: UInt64
    let diskWritten: UInt64
}

struct ProcUsage: Identifiable {
    let pid: pid_t
    let name: String
    let cpu: Double
    let memory: Int64
    var id: pid_t { pid }
}

enum AppFlag: Hashable {
    case cpu, memory, energy, idle(minutes: Int)

    var label: String {
        switch self {
        case .cpu: return "Processeur"
        case .memory: return "Mémoire"
        case .energy: return "Énergie"
        case .idle(let m): return m >= 120 ? "Inutilisée depuis \(m / 60) h" : "Inutilisée depuis \(m) min"
        }
    }

    var icon: String {
        switch self {
        case .cpu: return "cpu"
        case .memory: return "memorychip"
        case .energy: return "bolt.fill"
        case .idle: return "moon.zzz.fill"
        }
    }

    var color: Color {
        switch self {
        case .cpu, .memory, .energy: return AuraTheme.amber
        case .idle: return AuraTheme.legendDim
        }
    }

    var isIdle: Bool { if case .idle = self { return true } else { return false } }
}

struct AppUsage: Identifiable {
    let id: String                  // chemin de l'app (ou « webkit »)
    let name: String
    let app: NSRunningApplication?
    let iconPath: String?
    let isBackground: Bool          // app de barre des menus / sans fenêtre
    var cpu: Double = 0             // % d'un cœur (somme des processus)
    var cpuAvg: Double = 0
    var memory: Int64 = 0
    var energy: Double = 0          // watts
    var energyAvg: Double = 0
    var diskRead: Double = 0        // octets/s
    var diskWrite: Double = 0
    var processes: [ProcUsage] = []
    var history: [Double] = []
    var flags: [AppFlag] = []
    var idleMinutes: Int?
    var impact: Double = 0

    var pid: pid_t? { app?.processIdentifier }
    var launchDate: Date? { app?.launchDate }
    var isFrontmost: Bool { app?.isActive ?? false }
    var isHidden: Bool { app?.isHidden ?? false }
    var isGreedy: Bool { flags.contains { !$0.isIdle } }
    var isIdle: Bool { flags.contains { $0.isIdle } }
    var canQuit: Bool {
        guard let a = app else { return false }
        return a.processIdentifier != getpid() && a.bundleIdentifier != "com.apple.finder"
    }
    var icon: NSImage {
        if let a = app, let i = a.icon { return i }
        return NSWorkspace.shared.icon(forFile: iconPath ?? "/System/Applications/Utilities/Activity Monitor.app")
    }
}

/// Surveillance des applications ouvertes : consommation par app (sous-processus inclus),
/// détection des apps gourmandes ou inutilisées, fermeture.
@MainActor
final class AppActivityMonitor: ObservableObject {
    @Published private(set) var apps: [AppUsage] = []
    @Published private(set) var lastUpdate: Date?
    @Published private(set) var quitting: [pid_t: Date] = [:]
    @Published var message = ""

    /// Appelé quand une app reste gourmande en arrière-plan (alerte de santé).
    var onGreedy: ((AppUsage, String) -> Void)?

    private var previous: [pid_t: ProcSample] = [:]
    private var previousTime: Date?
    private var cpuHistory: [String: [Double]] = [:]
    private var energyHistory: [String: [Double]] = [:]
    private var lastActive: [pid_t: Date] = [:]
    private var greedySince: [String: Date] = [:]
    private let startDate = Date()
    private var timer: Timer?
    private var liveClients = 0
    private var sampling = false
    private var observers: [NSObjectProtocol] = []
    private let timebase: Double = {
        var tb = mach_timebase_info_data_t()
        mach_timebase_info(&tb)
        return Double(tb.numer) / Double(max(1, tb.denom))
    }()

    // MARK: Démarrage et cadence

    func start() {
        guard observers.isEmpty else { return }
        let nc = NSWorkspace.shared.notificationCenter
        observers.append(nc.addObserver(forName: NSWorkspace.didDeactivateApplicationNotification, object: nil, queue: .main) { [weak self] note in
            guard let pid = (note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication)?.processIdentifier else { return }
            Task { @MainActor in self?.lastActive[pid] = Date() }
        })
        for name in [NSWorkspace.didLaunchApplicationNotification, NSWorkspace.didTerminateApplicationNotification] {
            observers.append(nc.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
                Task { @MainActor in await self?.sample() }
            })
        }
        schedule()
        Task { await sample() }
    }

    /// Mesures rapides (toutes les 2 s) tant qu'un écran d'Aura les affiche.
    func beginLive() {
        liveClients += 1
        if liveClients == 1 {
            schedule()
            Task { await sample() }
        }
    }

    func endLive() {
        liveClients = max(0, liveClients - 1)
        if liveClients == 0 { schedule() }
    }

    private func schedule() {
        timer?.invalidate()
        let interval: TimeInterval = liveClients > 0 ? 2 : 20
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.sample() }
        }
    }

    // MARK: Lecture des processus

    /// Liste tous les processus de l'utilisateur avec leur consommation cumulée.
    nonisolated static func readAll() -> [ProcSample] {
        let count = proc_listallpids(nil, 0)
        guard count > 0 else { return [] }
        var pids = [pid_t](repeating: 0, count: Int(count) + 128)
        let n = pids.withUnsafeMutableBytes { buf in
            proc_listallpids(buf.baseAddress, Int32(buf.count))
        }
        guard n > 0 else { return [] }
        var out: [ProcSample] = []
        out.reserveCapacity(Int(n))
        var pathBuf = [CChar](repeating: 0, count: 4096)
        for pid in pids.prefix(Int(n)) where pid > 0 {
            guard proc_pidpath(pid, &pathBuf, UInt32(pathBuf.count)) > 0 else { continue }
            var info = rusage_info_v4()
            let rc = withUnsafeMutablePointer(to: &info) { ptr in
                ptr.withMemoryRebound(to: rusage_info_t?.self, capacity: 1) {
                    proc_pid_rusage(pid, RUSAGE_INFO_V4, $0)
                }
            }
            guard rc == 0 else { continue }     // processus d'un autre utilisateur (système)
            out.append(ProcSample(pid: pid, path: String(cString: pathBuf),
                                  cpuAbs: info.ri_user_time &+ info.ri_system_time,
                                  energyNJ: info.ri_billed_energy,
                                  footprint: info.ri_phys_footprint,
                                  diskRead: info.ri_diskio_bytesread,
                                  diskWritten: info.ri_diskio_byteswritten))
        }
        return out
    }

    // MARK: Analyse

    func sample() async {
        guard !sampling else { return }
        sampling = true
        defer { sampling = false }

        let running = NSWorkspace.shared.runningApplications.filter { $0.activationPolicy != .prohibited && !$0.isTerminated }
        let samples = await Task.detached(priority: .utility) { Self.readAll() }.value
        let now = Date()
        let dt = previousTime.map { now.timeIntervalSince($0) } ?? 0

        // 1. Les groupes : une entrée par application ouverte
        var groups: [String: AppUsage] = [:]
        var pidToKey: [pid_t: String] = [:]
        var bundleToKey: [String: String] = [:]
        var bundleNameToKey: [String: String] = [:]
        for a in running {
            let path = a.bundleURL?.standardizedFileURL.path
            let key = path ?? "pid:\(a.processIdentifier)"
            groups[key] = AppUsage(id: key,
                                   name: a.localizedName ?? (path.map { ($0 as NSString).lastPathComponent } ?? "App"),
                                   app: a, iconPath: path, isBackground: a.activationPolicy != .regular)
            pidToKey[a.processIdentifier] = key
            if let p = path {
                bundleToKey[p] = key
                bundleNameToKey[(p as NSString).lastPathComponent] = key
            }
        }

        // 2. Chaque processus est rattaché à son application
        let webKey = "webkit"
        var procs: [String: [ProcUsage]] = [:]
        var current: [pid_t: ProcSample] = [:]
        for s in samples {
            current[s.pid] = s
            var key = pidToKey[s.pid]
            if key == nil, let r = s.path.range(of: ".app/") {
                let bundle = String(s.path[..<r.lowerBound]) + ".app"
                key = bundleToKey[bundle] ?? bundleNameToKey[(bundle as NSString).lastPathComponent]
            }
            if key == nil && s.path.contains("com.apple.WebKit") {
                key = webKey
                if groups[webKey] == nil {
                    groups[webKey] = AppUsage(id: webKey, name: "Contenu web (onglets Safari et apps)", app: nil,
                                              iconPath: "/Applications/Safari.app", isBackground: false)
                }
            }
            guard let k = key, var g = groups[k] else { continue }

            var cpu = 0.0, energy = 0.0, rd = 0.0, wr = 0.0
            if dt > 0.3, let p = previous[s.pid], s.cpuAbs >= p.cpuAbs {
                cpu = Double(s.cpuAbs - p.cpuAbs) * timebase / (dt * 1e9) * 100
                if s.energyNJ >= p.energyNJ { energy = Double(s.energyNJ - p.energyNJ) / dt / 1e9 }
                if s.diskRead >= p.diskRead { rd = Double(s.diskRead - p.diskRead) / dt }
                if s.diskWritten >= p.diskWritten { wr = Double(s.diskWritten - p.diskWritten) / dt }
            }
            g.cpu += cpu
            g.energy += energy
            g.diskRead += rd
            g.diskWrite += wr
            g.memory += Int64(s.footprint)
            groups[k] = g
            procs[k, default: []].append(ProcUsage(pid: s.pid, name: (s.path as NSString).lastPathComponent,
                                                   cpu: cpu, memory: Int64(s.footprint)))
        }
        previous = current
        previousTime = now

        // 3. Historique, signaux d'alerte et score d'impact
        let ram = Double(ProcessInfo.processInfo.physicalMemory)
        var result: [AppUsage] = []
        for (k, var g) in groups {
            g.processes = (procs[k] ?? []).sorted { $0.cpu == $1.cpu ? $0.memory > $1.memory : $0.cpu > $1.cpu }
            if g.processes.isEmpty && g.memory == 0 && k == webKey { continue }

            if dt > 0.3 {
                cpuHistory[k, default: []].append(g.cpu)
                energyHistory[k, default: []].append(g.energy)
            }
            if (cpuHistory[k]?.count ?? 0) > 30 { cpuHistory[k]?.removeFirst() }
            if (energyHistory[k]?.count ?? 0) > 30 { energyHistory[k]?.removeFirst() }
            g.history = cpuHistory[k] ?? []
            let recent = g.history.suffix(10)
            g.cpuAvg = recent.isEmpty ? g.cpu : recent.reduce(0, +) / Double(recent.count)
            let recentE = (energyHistory[k] ?? []).suffix(10)
            g.energyAvg = recentE.isEmpty ? g.energy : recentE.reduce(0, +) / Double(recentE.count)

            var flags: [AppFlag] = []
            if g.cpuAvg > 50 { flags.append(.cpu) }
            if Double(g.memory) > max(2e9, 0.12 * ram) { flags.append(.memory) }
            if g.energyAvg > 2.0 { flags.append(.energy) }
            if let a = g.app, !a.isActive, a.activationPolicy == .regular {
                let since = lastActive[a.processIdentifier] ?? max(startDate, a.launchDate ?? startDate)
                let minutes = Int(now.timeIntervalSince(since) / 60)
                g.idleMinutes = minutes
                if minutes >= 60 && (g.memory > 400_000_000 || g.cpuAvg > 3) && g.canQuit {
                    flags.append(.idle(minutes: minutes))
                }
            }
            g.flags = flags
            g.impact = g.cpuAvg * 0.5 + Double(g.memory) / 1e9 * 10 + g.energyAvg * 8
            result.append(g)
        }
        apps = result.sorted { $0.impact > $1.impact }
        lastUpdate = now

        // Fermetures en cours : on oublie celles qui ont abouti
        let alive = Set(running.map(\.processIdentifier))
        quitting = quitting.filter { alive.contains($0.key) }

        checkGreedyInBackground(now)
    }

    /// Alerte quand une app non utilisée reste gourmande plus de 2 minutes.
    private func checkGreedyInBackground(_ now: Date) {
        var still: [String: Date] = [:]
        for a in apps where !a.isFrontmost && (a.flags.contains(.cpu) || a.flags.contains(.energy)) && a.canQuit {
            let since = greedySince[a.id] ?? now
            still[a.id] = since
            if now.timeIntervalSince(since) >= 120 {
                let what = a.flags.contains(.cpu) ? "\(Int(a.cpuAvg)) % de processeur" : "beaucoup d'énergie"
                onGreedy?(a, "\(a.name) utilise \(what) en arrière-plan depuis plus de 2 minutes.")
            }
        }
        greedySince = still
    }

    // MARK: Synthèse

    var regularApps: [AppUsage] { apps.filter { !$0.isBackground } }
    var greedyApps: [AppUsage] { apps.filter(\.isGreedy) }
    var idleApps: [AppUsage] { apps.filter(\.isIdle) }
    var totalMemory: Int64 { apps.reduce(0) { $0 + $1.memory } }
    var idleMemory: Int64 { idleApps.reduce(0) { $0 + $1.memory } }

    func explanation(_ a: AppUsage) -> String {
        var parts: [String] = []
        if a.flags.contains(.cpu) { parts.append("\(Int(a.cpuAvg)) % de processeur") }
        if a.flags.contains(.memory) { parts.append("\(Fmt.bytes(a.memory)) de mémoire") }
        if a.flags.contains(.energy) { parts.append("\(Self.watts(a.energyAvg)) d'énergie") }
        if let f = a.flags.first(where: \.isIdle) {
            let base = f.label.lowercased()
            parts.append(parts.isEmpty ? "\(base), occupe \(Fmt.bytes(a.memory))" : base)
        }
        let procs = a.processes.count > 1 ? " (\(a.processes.count) processus)" : ""
        return parts.joined(separator: ", ").capitalizedFirst + procs
    }

    static func watts(_ w: Double) -> String {
        w < 0.05 ? "0 W" : w.formatted(.number.precision(.fractionLength(1))) + " W"
    }

    // MARK: Actions

    func isQuitting(_ a: AppUsage) -> Bool { a.pid.map { quitting[$0] != nil } ?? false }

    /// L'app n'a pas répondu à la demande de fermeture depuis plus de 5 secondes.
    func isStuck(_ a: AppUsage) -> Bool {
        guard let p = a.pid, let d = quitting[p] else { return false }
        return Date().timeIntervalSince(d) > 5
    }

    func quit(_ a: AppUsage, force: Bool = false) {
        guard let app = a.app, a.canQuit else { return }
        let ok = force ? app.forceTerminate() : app.terminate()
        if ok {
            quitting[app.processIdentifier] = Date()
            message = force ? "\(a.name) fermée de force" : "Fermeture de \(a.name)…"
        } else {
            message = "\(a.name) refuse de se fermer : essaie « Forcer à quitter »."
        }
        Task {
            try? await Task.sleep(nanoseconds: 6_000_000_000)
            await sample()
        }
    }

    func quitIdleApps() {
        let list = idleApps
        list.forEach { quit($0) }
        message = "\(list.count) app(s) inutilisée(s) en cours de fermeture"
    }

    func quit(ids: Set<String>) {
        apps.filter { ids.contains($0.id) }.forEach { quit($0) }
    }

    func hide(_ a: AppUsage) {
        a.app?.hide()
    }

    func stopProcess(_ pid: pid_t, force: Bool) {
        Darwin.kill(pid, force ? SIGKILL : SIGTERM)
        Task {
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            await sample()
        }
    }
}
