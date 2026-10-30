import Foundation
import SwiftUI
import UserNotifications
import ServiceManagement

struct HealthAlert: Identifiable, Equatable {
    let id: String
    let title: String
    let message: String
    let icon: String
    let color: Color
    let module: Module?
}

enum CleanSchedule: String, CaseIterable, Identifiable {
    case off = "Désactivé", daily = "Chaque jour", weekly = "Chaque semaine", monthly = "Chaque mois"
    var id: String { rawValue }
    var interval: TimeInterval? {
        switch self {
        case .off: return nil
        case .daily: return 86_400
        case .weekly: return 7 * 86_400
        case .monthly: return 30 * 86_400
        }
    }
}

/// Alertes de santé, notifications, nettoyage planifié et lancement à la connexion.
@MainActor
final class HealthCenter: ObservableObject {
    @Published var activeAlert: HealthAlert?
    @Published var history: [(Date, HealthAlert)] = []

    @AppStorage("aura.alerts.enabled") var alertsEnabled = true
    @AppStorage("aura.alerts.diskPercent") var diskThreshold = 10.0
    @AppStorage("aura.alerts.temp") var tempThreshold = 95.0
    @AppStorage("aura.alerts.cpuHog") var cpuHogThreshold = 85.0
    @AppStorage("aura.schedule") private var scheduleRaw = CleanSchedule.weekly.rawValue
    @AppStorage("aura.schedule.last") private var lastAutoClean: Double = 0

    var schedule: CleanSchedule {
        get { CleanSchedule(rawValue: scheduleRaw) ?? .off }
        set { scheduleRaw = newValue.rawValue; objectWillChange.send() }
    }

    private var timer: Timer?
    private var silenced: [String: Date] = [:]
    private var hogStrikes: [Int32: Int] = [:]
    private weak var monitor: SystemMonitor?
    private weak var cleanup: CleanupEngine?

    private var canNotify: Bool { Bundle.main.bundleIdentifier != nil }

    func start(monitor: SystemMonitor, cleanup: CleanupEngine) {
        guard timer == nil else { return }
        self.monitor = monitor
        self.cleanup = cleanup
        if canNotify {
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
        }
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.tick() }
        }
        Task { await tick() }
    }

    private func tick() async {
        guard let m = monitor else { return }
        if alertsEnabled { evaluate(m) }
        await runScheduledCleanIfDue()
    }

    // MARK: Règles d'alerte

    private func evaluate(_ m: SystemMonitor) {
        if m.diskTotal > 0 {
            let freePct = Double(m.diskFree) / Double(m.diskTotal) * 100
            if freePct < diskThreshold {
                raise(HealthAlert(id: "disk", title: "Disque presque plein",
                                  message: "Il ne reste que \(Fmt.bytes(m.diskFree)) (\(Int(freePct)) %). Un nettoyage s'impose.",
                                  icon: "internaldrive.fill", color: .red, module: .smartScan))
            }
        }
        if m.memPressure > 0.92 && m.swapUsed > 3_000_000_000 {
            raise(HealthAlert(id: "ram", title: "Mémoire saturée",
                              message: "macOS utilise \(Fmt.bytes(m.swapUsed)) de swap : ferme des apps ou libère la RAM.",
                              icon: "memorychip", color: .orange, module: .monitor))
        }
        if let t = m.temps.hottest, t > tempThreshold {
            raise(HealthAlert(id: "temp", title: "Mac très chaud",
                              message: "Un capteur atteint \(Int(t)) °C. Vérifie les apps gourmandes et l'aération.",
                              icon: "thermometer.high", color: .red, module: .monitor))
        }
        if let h = m.battery.health, h < 0.8 {
            raise(HealthAlert(id: "battery", title: "Batterie usée",
                              message: "Capacité maximale à \(Int(h * 100)) % après \(m.battery.cycleCount ?? 0) cycles. Pense à la faire contrôler.",
                              icon: "battery.25", color: .orange, module: .monitor), silenceDays: 30)
        }
        // App qui monopolise le processeur pendant plusieurs relevés consécutifs
        var strikes: [Int32: Int] = [:]
        for p in m.processes where p.cpu > cpuHogThreshold && !["kernel_task", "WindowServer"].contains(p.name) {
            strikes[p.pid] = (hogStrikes[p.pid] ?? 0) + 1
            if strikes[p.pid]! >= 4 {
                raise(HealthAlert(id: "hog-\(p.name)", title: "\(p.name) monopolise le processeur",
                                  message: "\(Int(p.cpu)) % de CPU depuis plus de 2 minutes.",
                                  icon: "flame.fill", color: .orange, module: .monitor))
            }
        }
        hogStrikes = strikes
    }

    private func raise(_ a: HealthAlert, silenceDays: Double = 0.25) {
        if let until = silenced[a.id], until > Date() { return }
        silenced[a.id] = Date().addingTimeInterval(silenceDays * 86_400)
        activeAlert = a
        history.insert((Date(), a), at: 0)
        if history.count > 50 { history.removeLast() }
        notify(a.title, a.message)
    }

    func dismiss() { activeAlert = nil }

    func notify(_ title: String, _ body: String) {
        guard canNotify else { return }
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: nil))
    }

    // MARK: Nettoyage planifié

    var nextAutoClean: Date? {
        guard let i = schedule.interval else { return nil }
        return Date(timeIntervalSince1970: lastAutoClean + i)
    }

    private func runScheduledCleanIfDue() async {
        guard let interval = schedule.interval, let cleanup, !cleanup.isScanning, !cleanup.isCleaning else { return }
        if lastAutoClean == 0 { lastAutoClean = Date().timeIntervalSince1970; return }
        guard Date().timeIntervalSince1970 - lastAutoClean >= interval else { return }
        lastAutoClean = Date().timeIntervalSince1970
        let freed = await cleanup.autoClean()
        if freed > 0 { notify("Nettoyage automatique terminé", "\(Fmt.bytes(freed)) libérés (caches et journaux).") }
    }

    // MARK: Lancement à la connexion

    var launchAtLogin: Bool {
        get { SMAppService.mainApp.status == .enabled }
        set {
            do {
                if newValue { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            } catch {
                notify("Lancement à la connexion", "Impossible de modifier ce réglage : place Aura dans le dossier Applications.")
            }
            objectWillChange.send()
        }
    }
}
