import Foundation
import WatchKit

enum PhaseKind { case prep, work, rest }

struct Phase {
    let label: String
    let duration: TimeInterval
    let kind: PhaseKind
    let round: Int
    let total: Int
}

enum TimerMode: String, CaseIterable, Identifiable {
    case interval = "Intervalles"
    case emom = "EMOM"
    case tabata = "Tabata"
    case amrap = "AMRAP"
    case stopwatch = "Chrono"
    var id: String { rawValue }
}

struct TimerConfig {
    var work = 40
    var rest = 20
    var rounds = 8
    var minutes = 12
    var prep = 10
}

/// Moteur de minuterie : construit la liste des phases et les enchaîne avec retours haptiques.
@MainActor
final class TimerEngine: ObservableObject {
    @Published private(set) var phases: [Phase] = []
    @Published private(set) var index = 0
    @Published private(set) var remaining: TimeInterval = 0
    @Published private(set) var elapsed: TimeInterval = 0
    @Published private(set) var isRunning = false
    @Published private(set) var isFinished = false
    @Published private(set) var laps: [TimeInterval] = []
    @Published private(set) var mode: TimerMode = .interval

    private var timer: Timer?
    private var phaseEnd: Date?
    private var startDate: Date?
    private var accumulated: TimeInterval = 0
    private var lastBeepSecond = -1

    var current: Phase? { phases.indices.contains(index) ? phases[index] : nil }

    var roundText: String {
        guard let p = current, p.kind != .prep else { return "" }
        if mode == .emom { return "Minute \(p.round)/\(p.total)" }
        return p.total > 1 ? "\(p.round)/\(p.total)" : ""
    }

    func configure(mode: TimerMode, config c: TimerConfig) {
        stopTimer()
        self.mode = mode
        isRunning = false
        isFinished = false
        index = 0
        elapsed = 0
        accumulated = 0
        laps = []
        var p: [Phase] = []
        if mode != .stopwatch, c.prep > 0 {
            p.append(Phase(label: "Prêt", duration: TimeInterval(c.prep), kind: .prep, round: 0, total: 0))
        }
        switch mode {
        case .interval, .tabata:
            let w = mode == .tabata ? 20 : c.work
            let r = mode == .tabata ? 10 : c.rest
            let n = mode == .tabata ? 8 : c.rounds
            for i in 1...max(1, n) {
                p.append(Phase(label: "Effort", duration: TimeInterval(w), kind: .work, round: i, total: n))
                if i < n && r > 0 {
                    p.append(Phase(label: "Récup", duration: TimeInterval(r), kind: .rest, round: i, total: n))
                }
            }
        case .emom:
            for i in 1...max(1, c.minutes) {
                p.append(Phase(label: "EMOM", duration: 60, kind: .work, round: i, total: c.minutes))
            }
        case .amrap:
            p.append(Phase(label: "AMRAP", duration: TimeInterval(c.minutes * 60), kind: .work, round: 1, total: 1))
        case .stopwatch:
            break
        }
        phases = p
        remaining = p.first?.duration ?? 0
    }

    func start() {
        guard !isRunning, !isFinished else { return }
        if mode == .stopwatch {
            startDate = Date()
        } else {
            phaseEnd = Date().addingTimeInterval(remaining)
        }
        isRunning = true
        WKInterfaceDevice.current().play(.start)
        let t = Timer(timeInterval: 0.1, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tick() }
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func pause() {
        guard isRunning else { return }
        stopTimer()
        isRunning = false
        if mode == .stopwatch, let s = startDate {
            accumulated += Date().timeIntervalSince(s)
        } else if let end = phaseEnd {
            remaining = max(0, end.timeIntervalSinceNow)
        }
        WKInterfaceDevice.current().play(.stop)
    }

    func lap() {
        guard mode == .stopwatch, isRunning else { return }
        laps.append(elapsed)
        WKInterfaceDevice.current().play(.click)
    }

    func reset() {
        stopTimer()
        isRunning = false
        isFinished = false
        index = 0
        accumulated = 0
        elapsed = 0
        laps = []
        remaining = phases.first?.duration ?? 0
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    private func tick() {
        if mode == .stopwatch {
            if let s = startDate { elapsed = accumulated + Date().timeIntervalSince(s) }
            return
        }
        guard let end = phaseEnd else { return }
        remaining = max(0, end.timeIntervalSinceNow)
        let s = Int(ceil(remaining))
        if (1...3).contains(s), s != lastBeepSecond {
            lastBeepSecond = s
            WKInterfaceDevice.current().play(.click)
        }
        if end.timeIntervalSinceNow <= 0 { advance(from: end) }
    }

    private func advance(from previousEnd: Date) {
        index += 1
        lastBeepSecond = -1
        guard index < phases.count else {
            stopTimer()
            isRunning = false
            isFinished = true
            remaining = 0
            WKInterfaceDevice.current().play(.success)
            return
        }
        let next = phases[index]
        phaseEnd = previousEnd.addingTimeInterval(next.duration)
        remaining = next.duration
        WKInterfaceDevice.current().play(next.kind == .work ? .start : .stop)
    }
}
