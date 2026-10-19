import Foundation
import SwiftUI
import WatchKit
import AVFoundation
import WatchConnectivity
import HealthKit

// MARK: - Séance guidée envoyée depuis l'appli Foulée (iPhone)

/// Une étape de séance : distance (m) ou durée (s), fourchette d'allure en s/km.
struct GStep: Codable {
    let n: String          // nom affiché et annoncé
    let k: String          // warm, work, rest, cool, run
    let d: Double?         // distance en mètres
    let t: Double?         // durée en secondes
    let lo: Double?        // allure la plus rapide de la cible (s/km)
    let hi: Double?        // allure la plus lente de la cible (s/km)
    let tp: Double?        // allure visée pour une fraction (s/km)
}

struct GPlan: Codable, Identifiable {
    let id: String
    let name: String
    let date: String?
    let steps: [GStep]
}

/// Séances reçues de l'iPhone, gardées sur la montre (10 dernières).
@MainActor
final class PlanStore: NSObject, ObservableObject {
    @Published private(set) var plans: [GPlan] = []
    @Published var lastReceived: String?
    private let key = "foulee.guided.plans"

    override init() {
        super.init()
        if let data = UserDefaults.standard.data(forKey: key),
           let list = try? JSONDecoder().decode([GPlan].self, from: data) {
            plans = list
        }
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    func add(json: String) {
        guard let data = json.data(using: .utf8),
              let plan = try? JSONDecoder().decode(GPlan.self, from: data),
              !plan.steps.isEmpty else { return }
        plans.removeAll { $0.id == plan.id }
        plans.insert(plan, at: 0)
        if plans.count > 10 { plans = Array(plans.prefix(10)) }
        if let out = try? JSONEncoder().encode(plans) {
            UserDefaults.standard.set(out, forKey: key)
        }
        lastReceived = plan.name
        WKInterfaceDevice.current().play(.notification)
    }

    func remove(_ plan: GPlan) {
        plans.removeAll { $0.id == plan.id }
        if let out = try? JSONEncoder().encode(plans) {
            UserDefaults.standard.set(out, forKey: key)
        }
    }

    /// Footing libre réglé sur la montre.
    static func free(km: Int, pace: Int) -> GPlan {
        let lo = Double(pace) * 0.97
        let hi = Double(pace) * 1.04
        let step = GStep(n: "Footing \(km) km", k: "run", d: Double(km) * 1000, t: nil, lo: lo, hi: hi, tp: nil)
        return GPlan(id: "libre-\(km)-\(pace)", name: "Footing \(km) km", date: nil, steps: [step])
    }
}

extension PlanStore: WCSessionDelegate {
    nonisolated func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}

    nonisolated func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        if let json = userInfo["plan"] as? String {
            Task { @MainActor in self.add(json: json) }
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {
        if let json = message["plan"] as? String {
            Task { @MainActor in self.add(json: json) }
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) {
        if let json = applicationContext["plan"] as? String {
            Task { @MainActor in self.add(json: json) }
        }
    }
}

// MARK: - Voix

/// Synthèse vocale française. Une seule instance gardée en vie pendant toute la course.
@MainActor
final class Speaker: NSObject, AVSpeechSynthesizerDelegate {
    private let synth = AVSpeechSynthesizer()
    private let voice = AVSpeechSynthesisVoice(language: "fr-FR")
    var enabled = true

    override init() {
        super.init()
        synth.delegate = self
    }

    func say(_ text: String, queue: Bool = false) {
        guard enabled, !text.isEmpty else { return }
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
            try session.setActive(true)
        } catch {
            print("Audio session error: \(error)")
        }
        if !queue && synth.isSpeaking { synth.stopSpeaking(at: .word) }
        let u = AVSpeechUtterance(string: text)
        u.voice = voice
        u.rate = AVSpeechUtteranceDefaultSpeechRate * 1.02
        synth.speak(u)
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in
            if !self.synth.isSpeaking {
                try? AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
            }
        }
    }
}

// MARK: - Formats parlés et affichés

enum Say {
    static func pace(_ p: Double?) -> String {
        guard let p, p.isFinite, p > 0 else { return "inconnue" }
        let m = Int(p) / 60, s = Int(p.rounded()) % 60
        return s == 0 ? "\(m) minutes" : String(format: "%d minutes %02d", m, s)
    }
    static func dur(_ v: Double) -> String {
        let s = Int(v.rounded()), h = s / 3600, m = (s % 3600) / 60, r = s % 60
        var parts: [String] = []
        if h > 0 { parts.append("\(h) heure\(h > 1 ? "s" : "")") }
        if m > 0 { parts.append("\(m) minute\(m > 1 ? "s" : "")") }
        if h == 0 && r > 0 { parts.append("\(r) seconde\(r > 1 ? "s" : "")") }
        return parts.isEmpty ? "0 seconde" : parts.joined(separator: " ")
    }
    static func dist(_ m: Double) -> String {
        if m >= 1000 {
            let km = (m / 100).rounded() / 10
            return String(format: "%.1f", km).replacingOccurrences(of: ".0", with: "").replacingOccurrences(of: ".", with: ",") + " kilomètres"
        }
        return "\(Int((m / 10).rounded()) * 10) mètres"
    }
    static func paceShort(_ p: Double?) -> String {
        guard let p, p.isFinite, p > 0, p < 1800 else { return "–" }
        let s = Int(p.rounded())
        return String(format: "%d:%02d", s / 60, s % 60)
    }
    static func clock(_ v: Double) -> String {
        let s = max(0, Int(v.rounded())), h = s / 3600
        return h > 0 ? String(format: "%d:%02d:%02d", h, (s % 3600) / 60, s % 60) : String(format: "%d:%02d", s / 60, s % 60)
    }
}

// MARK: - Moteur de la course guidée

@MainActor
final class GuidedEngine: ObservableObject {
    @Published private(set) var plan: GPlan?
    @Published private(set) var si = 0
    @Published private(set) var elapsed: Double = 0
    @Published private(set) var distance: Double = 0
    @Published private(set) var paceNow: Double?
    @Published private(set) var running = false
    @Published private(set) var paused = false
    @Published private(set) var finished = false
    @Published private(set) var splits: [Double] = []
    @Published var autoEvery = 0          // point vocal automatique (min), 0 = non

    let speaker = Speaker()
    private weak var workout: WorkoutManager?
    private var timer: Timer?
    private var startDate = Date()
    private var pausedTotal: Double = 0
    private var pauseStart: Date?
    private var samples: [(t: Double, d: Double)] = []
    private var stepT0: Double = 0
    private var stepD0: Double = 0
    private var half = false
    private var near = false
    private var tenDone = false
    private var lastBeep = -1
    private var lastKm = 0
    private var lastWarn: Double = 0
    private var lastAuto: Double = 0

    var step: GStep? {
        guard let p = plan, p.steps.indices.contains(si) else { return nil }
        return p.steps[si]
    }
    var stepElapsed: Double { elapsed - stepT0 }
    var stepDistance: Double { distance - stepD0 }
    var stepFraction: Double {
        guard let s = step else { return 0 }
        if let d = s.d, d > 0 { return stepDistance / d }
        if let t = s.t, t > 0 { return stepElapsed / t }
        return 0
    }
    var stepRemaining: Double {
        guard let s = step else { return 0 }
        if let d = s.d { return max(0, d - stepDistance) }
        if let t = s.t { return max(0, t - stepElapsed) }
        return 0
    }
    var average: Double? { distance > 50 ? elapsed / (distance / 1000) : nil }

    func verdictColor(_ p: Double?) -> Color {
        guard let p, let s = step, let lo = s.lo, let hi = s.hi else { return .white }
        if p < lo * 0.985 { return .orange }
        if p > hi * 1.015 { return Color(red: 0.96, green: 0.49, blue: 0.54) }
        return .green
    }

    func load(_ plan: GPlan) {
        self.plan = plan
        si = 0; elapsed = 0; distance = 0; paceNow = nil
        running = false; paused = false; finished = false; splits = []
    }

    func start(workout: WorkoutManager) {
        guard let p = plan, !running else { return }
        self.workout = workout
        startDate = Date(); pausedTotal = 0; pauseStart = nil
        samples = []; stepT0 = 0; stepD0 = 0; lastKm = 0; lastWarn = 0; lastAuto = 0
        half = false; near = false; tenDone = false; lastBeep = -1
        running = true; finished = false
        WKInterfaceDevice.current().play(.start)
        speaker.say("C’est parti. \(intro(p.steps[0]))")
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
    }

    func togglePause() {
        guard running else { return }
        if paused {
            if let ps = pauseStart { pausedTotal += Date().timeIntervalSince(ps) }
            pauseStart = nil; paused = false
            workout?.resume()
            speaker.say("Reprise.")
        } else {
            pauseStart = Date(); paused = true
            workout?.pause()
            speaker.say("Pause.")
        }
    }

    func stop() {
        timer?.invalidate(); timer = nil
        running = false
    }

    private func remainingWork() -> Int {
        guard let p = plan else { return 0 }
        return p.steps.dropFirst(si + 1).filter { $0.k == "work" }.count
    }

    private func intro(_ s: GStep) -> String {
        let target: String
        if let lo = s.lo, let hi = s.hi {
            target = " Allure cible : \(Say.pace(lo)) à \(Say.pace(hi)) au kilomètre."
        } else { target = "" }
        switch s.k {
        case "work":
            var t = s.n
            if let d = s.d { t += " : \(Say.dist(d))" } else if let du = s.t { t += " : \(Say.dur(du))" }
            t += "."
            if let tp = s.tp { t += " Vise \(Say.pace(tp)) au kilomètre." } else { t += " À fond mais relâché." }
            return t
        case "rest":
            let n = remainingWork()
            return "Récupération, \(Say.dur(s.t ?? 60)) au trot." + (n > 0 ? " Encore \(n) fraction\(n > 1 ? "s" : "")." : "")
        case "warm":
            return "Échauffement, \(Say.dur(s.t ?? 600)) en facile.\(target)"
        case "cool":
            return "Retour au calme, \(Say.dur(s.t ?? 600)) très facile."
        default:
            let amount = s.d.map { Say.dist($0) } ?? Say.dur(s.t ?? 0)
            return "\(amount) au programme.\(target)"
        }
    }

    private func verdict(_ p: Double, _ s: GStep) -> String {
        guard let lo = s.lo, let hi = s.hi else { return "" }
        if p < lo * 0.985 { return "trop rapide, ralentis de \(Int((lo - p).rounded())) secondes au kilomètre" }
        if p > hi * 1.015 { return "un peu lent, accélère de \(Int((p - hi).rounded())) secondes au kilomètre" }
        return "dans la cible"
    }

    private func pace(window: Double) -> Double? {
        guard let last = samples.last else { return nil }
        var i = samples.count - 2
        while i > 0 && last.t - samples[i].t < window { i -= 1 }
        guard i >= 0 else { return nil }
        let dd = last.d - samples[i].d, dt = last.t - samples[i].t
        return dd > 15 && dt > 5 ? dt / (dd / 1000) : nil
    }

    private func tick() {
        guard running, !paused else { return }
        elapsed = Date().timeIntervalSince(startDate) - pausedTotal
        distance = workout?.distance ?? distance
        samples.append((elapsed, distance))
        if samples.count > 900 { samples.removeFirst(samples.count - 900) }
        paceNow = pace(window: 30)
        check()
    }

    private func check() {
        guard let s = step else { return }
        let frac = stepFraction, rem = stepRemaining
        // fin d'étape au temps : bips des 3 dernières secondes
        if s.d == nil, s.t != nil {
            let r = Int(ceil(rem))
            if r >= 1 && r <= 3 && r != lastBeep { lastBeep = r; WKInterfaceDevice.current().play(.click) }
            if s.k == "rest" && (s.t ?? 0) >= 30 && r == 10 && !tenDone { tenDone = true; speaker.say("Prêt, 10 secondes.") }
        }
        if !half && frac >= 0.5 && (s.k == "work" || s.k == "run") && ((s.t ?? 0) >= 20 || (s.d ?? 0) >= 200) {
            half = true
            var msg = s.k == "work" ? "Moitié de la fraction." : "Moitié."
            let p: Double? = s.d != nil && stepDistance > 50 ? stepElapsed / (stepDistance / 1000) : pace(window: 20)
            if s.d != nil { msg += " Temps \(Say.dur(stepElapsed))." }
            if let p, s.lo != nil { msg += " Allure \(Say.pace(p)), \(verdict(p, s))." }
            speaker.say(msg)
        }
        if !near, s.k == "work", let d = s.d, d >= 400, rem <= 100, rem > 0 {
            near = true
            speaker.say("Plus que 100 mètres.")
        }
        if frac >= 1 { next(auto: true); return }
        if s.k == "run" || s.k == "warm" || s.k == "cool" {
            let km = Int(distance / 1000)
            if km > lastKm {
                lastKm = km
                let split = elapsed - splits.reduce(0, +)
                splits.append(split)
                let avg = elapsed / (distance / 1000)
                var msg = "Kilomètre \(km) en \(Say.dur(split)). Allure moyenne \(Say.pace(avg))"
                if s.lo != nil { msg += ", \(verdict(split, s))" }
                msg += "."
                if let d = s.d, d - stepDistance >= 500 {
                    let r = d - stepDistance
                    msg += " Encore \(Say.dist(r)), environ \(Say.dur(r / 1000 * avg))."
                }
                speaker.say(msg, queue: true)
                WKInterfaceDevice.current().play(.click)
                lastWarn = elapsed
            }
        }
        if let pn = pace(window: 45), let lo = s.lo, let hi = s.hi, s.k != "rest",
           elapsed - lastWarn > 120, stepElapsed > 60, (pn < lo * 0.95 || pn > hi * 1.06) {
            lastWarn = elapsed
            WKInterfaceDevice.current().play(pn < lo ? .directionDown : .directionUp)
            speaker.say("Allure \(Say.pace(pn)) : \(verdict(pn, s)).")
        }
        if autoEvery > 0 && elapsed - lastAuto > Double(autoEvery * 60) {
            lastAuto = elapsed
            status()
        }
    }

    func next(auto: Bool = false) {
        guard let p = plan, let s = step else { return }
        var msg = ""
        if s.k == "work", let r = s.n.split(separator: " ").dropFirst().first {
            let pc: Double? = stepDistance > 50 ? stepElapsed / (stepDistance / 1000) : nil
            msg = "Fin de la fraction \(r). " + (s.d != nil ? Say.dur(stepElapsed) : Say.dist(stepDistance))
            if let pc, s.tp != nil { msg += ", allure \(Say.pace(pc)), \(verdict(pc, s))" }
            msg += ". "
        }
        si += 1
        stepT0 = elapsed; stepD0 = distance
        half = false; near = false; tenDone = false; lastBeep = -1
        if si >= p.steps.count {
            finished = true
            stop()
            WKInterfaceDevice.current().play(.success)
            speaker.say("\(msg)Séance terminée, bravo ! \(Say.dist(distance)) en \(Say.dur(elapsed)).")
            return
        }
        let n = p.steps[si]
        WKInterfaceDevice.current().play(n.k == "work" ? .start : .stop)
        speaker.say(msg + intro(n))
    }

    func status() {
        guard let s = step else { speaker.say("\(Say.dist(distance)) en \(Say.dur(elapsed))."); return }
        var msg = s.k == "work" ? "\(s.n). " : ""
        msg += "\(Say.dist(distance)) en \(Say.dur(elapsed)). "
        if let pn = pace(window: 30) {
            msg += "Allure actuelle \(Say.pace(pn))" + (s.lo != nil ? ", \(verdict(pn, s))" : "") + ". "
        } else if let avg = average {
            msg += "Allure moyenne \(Say.pace(avg)). "
        }
        let rem = stepRemaining
        if rem > 0 { msg += "Il reste " + (s.d != nil ? Say.dist(rem) : Say.dur(rem)) + "." }
        speaker.say(msg)
    }
}

// MARK: - Écrans

struct GuidedListView: View {
    @EnvironmentObject var store: PlanStore
    @State private var km = 8
    @State private var pace = 345   // 5:45 /km

    var body: some View {
        List {
            if store.plans.isEmpty {
                Text("Envoie une séance depuis Foulée sur l’iPhone : séance › 🎧 Guidée › ⌚ Envoyer à l’Apple Watch.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section("Reçues de l’iPhone") {
                ForEach(store.plans) { p in
                    NavigationLink {
                        GuidedRunView(plan: p)
                    } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name).font(.headline).lineLimit(2)
                            Text("\(p.steps.count) étape\(p.steps.count > 1 ? "s" : "")\(p.date.map { " · " + $0 } ?? "")")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    .swipeActions { Button(role: .destructive) { store.remove(p) } label: { Image(systemName: "trash") } }
                }
            }
            Section("Footing libre") {
                Stepper("\(km) km", value: $km, in: 2...42)
                Stepper("Allure \(Say.paceShort(Double(pace)))", value: $pace, in: 210...480, step: 5)
                NavigationLink {
                    GuidedRunView(plan: PlanStore.free(km: km, pace: pace))
                } label: {
                    Label("Démarrer", systemImage: "figure.run")
                }
                .foregroundStyle(.green)
            }
        }
        .navigationTitle("Course guidée")
    }
}

struct GuidedRunView: View {
    let plan: GPlan
    @EnvironmentObject var engine: GuidedEngine
    @EnvironmentObject var workout: WorkoutManager
    @Environment(\.dismiss) private var dismiss
    @State private var started = false
    @State private var confirmEnd = false

    var body: some View {
        ScrollView {
            VStack(spacing: 4) {
                if engine.finished {
                    Image(systemName: "checkmark.circle.fill").font(.largeTitle).foregroundStyle(.green)
                    Text("\(Say.dist(engine.distance))").font(.headline)
                    Text("\(Say.clock(engine.elapsed)) · \(Say.paceShort(engine.average))/km").font(.footnote)
                    if !engine.splits.isEmpty {
                        Text(engine.splits.enumerated().map { "km \($0.offset + 1) \(Say.paceShort($0.element))" }.joined(separator: " · "))
                            .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }
                    Button("Enregistrer") {
                        Task { await workout.end(); dismiss() }
                    }
                    .tint(.green)
                } else {
                    HStack {
                        Text(engine.step?.n ?? plan.name).font(.footnote).lineLimit(1)
                        Spacer()
                        Text("\(min(engine.si + 1, plan.steps.count))/\(plan.steps.count)").font(.caption2).foregroundStyle(.secondary)
                    }
                    Text(Say.paceShort(engine.paceNow))
                        .font(.system(size: 44, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(engine.verdictColor(engine.paceNow))
                    if let s = engine.step, let lo = s.lo, let hi = s.hi {
                        Text("cible \(Say.paceShort(lo))–\(Say.paceShort(hi))").font(.caption2).foregroundStyle(.secondary)
                    }
                    HStack {
                        VStack { Text(String(format: "%.2f", engine.distance / 1000)).font(.headline).monospacedDigit(); Text("km").font(.caption2) }
                        Spacer()
                        VStack { Text(Say.clock(engine.elapsed)).font(.headline).monospacedDigit(); Text("temps").font(.caption2) }
                        Spacer()
                        VStack {
                            Text(engine.step?.d != nil ? "\(Int(engine.stepRemaining)) m" : Say.clock(engine.stepRemaining))
                                .font(.headline).monospacedDigit()
                            Text("reste").font(.caption2)
                        }
                    }
                    ProgressView(value: min(1, max(0, engine.stepFraction))).tint(Color(red: 0.96, green: 0.49, blue: 0.54))
                    if !started {
                        Picker("Point vocal", selection: $engine.autoEvery) {
                            Text("km + à la demande").tag(0)
                            Text("toutes les 5 min").tag(5)
                            Text("toutes les 10 min").tag(10)
                        }
                        Button("Démarrer") {
                            started = true
                            Task {
                                await workout.requestAuthorization()
                                await workout.start(activity: .running)
                                engine.load(plan)
                                engine.start(workout: workout)
                            }
                        }
                        .tint(.green)
                    } else {
                        Button { engine.status() } label: { Label("Où j’en suis ?", systemImage: "speaker.wave.2.fill") }
                            .tint(Color(red: 0.96, green: 0.49, blue: 0.54))
                        HStack(spacing: 6) {
                            Button { engine.togglePause() } label: { Image(systemName: engine.paused ? "play.fill" : "pause.fill") }
                            Button { engine.next() } label: { Image(systemName: "forward.end.fill") }
                            Button(role: .destructive) { confirmEnd = true } label: { Image(systemName: "stop.fill") }
                        }
                    }
                }
            }
            .padding(.horizontal, 4)
        }
        .navigationBarBackButtonHidden(started && !engine.finished)
        .confirmationDialog("Terminer la course ?", isPresented: $confirmEnd) {
            Button("Terminer et enregistrer") {
                engine.stop()
                Task { await workout.end(); dismiss() }
            }
            Button("Continuer", role: .cancel) {}
        }
        .onAppear { if !started { engine.load(plan) } }
    }
}
