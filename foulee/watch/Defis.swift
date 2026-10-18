import SwiftUI
import WatchKit
import HealthKit

// MARK: - Modèle (identique à l'appli Foulée iPhone/iPad)

struct DefiItem: Hashable {
    let name: String
    let reps: Int
}

struct Defi: Identifiable, Hashable {
    let id: String
    let name: String
    let alt: Int
    let items: [DefiItem]
    let levels: [Int]   // nombre de tours par niveau
}

let levelNames = ["Base", "★", "★★"]
struct Feel: Identifiable { let id: Int; let emoji: String; let label: String }
let feelLabels = [Feel(id: 1, emoji: "😎", label: "Trop facile"), Feel(id: 2, emoji: "👌", label: "Parfait"),
                  Feel(id: 3, emoji: "😤", label: "Difficile"), Feel(id: 4, emoji: "🥵", label: "Trop dur")]

let defis: [Defi] = [
    Defi(id: "ventoux", name: "Ventoux", alt: 1910,
         items: [.init(name: "Swings", reps: 15), .init(name: "Goblet squats", reps: 10), .init(name: "Pompes", reps: 10), .init(name: "Mountain climbers", reps: 20)],
         levels: [3, 4, 5]),
    Defi(id: "puy", name: "Puy de Dôme", alt: 1465,
         items: [.init(name: "Burpees", reps: 10), .init(name: "Fentes alternées", reps: 20), .init(name: "Dead bugs", reps: 20), .init(name: "Pompes", reps: 10)],
         levels: [3, 4, 5]),
    Defi(id: "aneto", name: "Aneto", alt: 3404,
         items: [.init(name: "Swings", reps: 20), .init(name: "Goblet squats", reps: 15), .init(name: "Fentes bulgares", reps: 10), .init(name: "Mollets excentriques", reps: 20)],
         levels: [3, 4, 5]),
    Defi(id: "etna", name: "Etna", alt: 3357,
         items: [.init(name: "Pompes", reps: 12), .init(name: "Rowing KB", reps: 20), .init(name: "Clean & press", reps: 10), .init(name: "Roue abdo genoux", reps: 10)],
         levels: [3, 4, 5]),
    Defi(id: "blanc", name: "Mont Blanc", alt: 4806,
         items: [.init(name: "Swings", reps: 20), .init(name: "Thrusters", reps: 12), .init(name: "Burpees", reps: 10), .init(name: "Rowing KB", reps: 16), .init(name: "Roue abdo", reps: 10)],
         levels: [3, 4, 5]),
    Defi(id: "kili", name: "Kilimandjaro", alt: 5895,
         items: [.init(name: "Swings", reps: 25), .init(name: "Goblet squats", reps: 20), .init(name: "Pompes", reps: 15), .init(name: "Fentes alternées", reps: 20), .init(name: "Mountain climbers", reps: 30), .init(name: "Burpees", reps: 10)],
         levels: [3, 4, 5])
]

func clock(_ t: Double, tenths: Bool = false) -> String {
    let s = Int(t)
    let base = String(format: "%d:%02d", s / 60, s % 60)
    return tenths ? base + ".\(Int((t - Double(s)) * 10))" : base
}

// MARK: - Records (stockés sur la montre)

struct DefiRecord: Codable {
    var date: Date
    var time: Double
    var splits: [Double]   // temps cumulés à la fin de chaque tour
    var feel: Int?
}

@MainActor
final class DefiStore: ObservableObject {
    @Published private(set) var records: [String: [DefiRecord]] = [:]
    private let storageKey = "foulee.defis.v1"

    init() {
        if let data = UserDefaults.standard.data(forKey: storageKey),
           let r = try? JSONDecoder().decode([String: [DefiRecord]].self, from: data) {
            records = r
        }
    }

    private static func key(_ id: String, _ lv: Int) -> String { "\(id)#\(lv)" }

    func history(_ id: String, _ lv: Int) -> [DefiRecord] { records[Self.key(id, lv)] ?? [] }

    func best(_ id: String, _ lv: Int) -> DefiRecord? {
        history(id, lv).min { $0.time < $1.time }
    }

    func unlocked(_ id: String, _ lv: Int) -> Bool {
        lv == 0 || history(id, lv - 1).contains { ($0.feel ?? 9) <= 2 }
    }

    func highestUnlocked(_ d: Defi) -> Int {
        (0..<d.levels.count).last { unlocked(d.id, $0) } ?? 0
    }

    func add(_ id: String, _ lv: Int, _ r: DefiRecord) {
        records[Self.key(id, lv), default: []].append(r)
        persist()
    }

    func setLastFeel(_ id: String, _ lv: Int, _ feel: Int) {
        let k = Self.key(id, lv)
        guard var list = records[k], !list.isEmpty else { return }
        list[list.count - 1].feel = feel
        records[k] = list
        persist()
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(records) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }
}

// MARK: - Liste et détail

struct DefiListView: View {
    @EnvironmentObject var store: DefiStore

    var body: some View {
        List(defis) { d in
            NavigationLink {
                DefiDetailView(defi: d)
            } label: {
                VStack(alignment: .leading, spacing: 2) {
                    Text("⛰️ \(d.name)").font(.headline)
                    let lv = store.highestUnlocked(d)
                    if let b = store.best(d.id, lv) {
                        Text("\(levelNames[lv]) · record \(clock(b.time))").font(.footnote).foregroundStyle(.secondary)
                    } else {
                        Text("\(d.alt) m · pas encore tenté").font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Défis")
    }
}

struct DefiDetailView: View {
    let defi: Defi
    @EnvironmentObject var store: DefiStore
    @State private var level = 0
    @State private var go = false

    var body: some View {
        List {
            Picker("Niveau", selection: $level) {
                ForEach(0..<defi.levels.count, id: \.self) { i in
                    Text(store.unlocked(defi.id, i)
                         ? "\(levelNames[i]) · \(defi.levels[i]) tours"
                         : "\(levelNames[i]) 🔒")
                        .tag(i)
                }
            }
            .onChange(of: level) { _, new in
                if !store.unlocked(defi.id, new) { level = store.highestUnlocked(defi) }
            }

            Section("Par tour") {
                ForEach(defi.items, id: \.self) { it in
                    HStack { Text(it.name); Spacer(); Text("\(it.reps)").bold() }
                }
            }

            Section {
                if let b = store.best(defi.id, level) {
                    LabeledContent("Record", value: clock(b.time))
                    LabeledContent("Tentatives", value: "\(store.history(defi.id, level).count)")
                } else {
                    Text("Premier passage : fixe ta référence").foregroundStyle(.secondary)
                }
                Button("▶ Go") { go = true }
                    .foregroundStyle(.green)
                    .font(.headline)
            }
        }
        .navigationTitle(defi.name)
        .onAppear { level = store.highestUnlocked(defi) }
        .navigationDestination(isPresented: $go) {
            DefiRunView(defi: defi, level: level) { go = false }
        }
    }
}

// MARK: - Défi en cours

struct DefiRunView: View {
    let defi: Defi
    let level: Int
    let onClose: () -> Void

    @EnvironmentObject var store: DefiStore
    @EnvironmentObject var workout: WorkoutManager

    @State private var startDate: Date?
    @State private var accumulated: Double = 0
    @State private var splits: [Double] = []
    @State private var finished = false
    @State private var result: DefiRecord?
    @State private var previousBest: DefiRecord?
    @State private var feelGiven = false

    private var rounds: Int { defi.levels[level] }
    private var isRunning: Bool { startDate != nil && !finished }

    private func elapsed(at now: Date) -> Double {
        accumulated + (startDate.map { now.timeIntervalSince($0) } ?? 0)
    }

    var body: some View {
        Group {
            if let r = result {
                resultView(r)
            } else {
                runView
            }
        }
        .navigationBarBackButtonHidden(true)
        .task {
            previousBest = store.best(defi.id, level)
            await workout.requestAuthorization()
            await workout.start(activity: .functionalStrengthTraining)
            startDate = Date()
            WKInterfaceDevice.current().play(.start)
        }
    }

    // Écran pendant l'effort
    private var runView: some View {
        TimelineView(.periodic(from: .now, by: 0.1)) { ctx in
            let t = elapsed(at: ctx.date)
            VStack(spacing: 3) {
                HStack {
                    Text("Tour \(min(splits.count + 1, rounds))/\(rounds)")
                        .font(.headline)
                        .foregroundStyle(Color(red: 0.78, green: 0.96, blue: 0.2))
                    Spacer()
                    Label("\(Int(workout.heartRate))", systemImage: "heart.fill")
                        .font(.footnote).foregroundStyle(.red)
                }
                Text(clock(t, tenths: true))
                    .font(.system(size: 38, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .minimumScaleFactor(0.6)
                ghostText
                    .font(.footnote)
                Button {
                    lap(at: t)
                } label: {
                    Text(splits.count + 1 >= rounds ? "🏁 Terminé" : "✓ Tour")
                        .font(.title3.bold())
                        .frame(maxWidth: .infinity)
                }
                .tint(Color(red: 0.78, green: 0.96, blue: 0.2))
                .disabled(startDate == nil)
                HStack {
                    Button {
                        togglePause()
                    } label: {
                        Image(systemName: startDate == nil ? "play.fill" : "pause.fill")
                    }
                    Button(role: .destructive) {
                        quit()
                    } label: {
                        Image(systemName: "xmark")
                    }
                }
                .font(.footnote)
            }
        }
    }

    @ViewBuilder private var ghostText: some View {
        if let pb = previousBest, pb.splits.count == rounds {
            if let last = splits.last {
                let delta = last - pb.splits[splits.count - 1]
                Text(delta <= 0 ? "▲ \(clock(-delta)) d’avance" : "▼ \(clock(delta)) de retard")
                    .foregroundStyle(delta <= 0 ? .green : .orange)
            } else {
                Text("Record : \(clock(pb.time))").foregroundStyle(.secondary)
            }
        } else {
            Text(defi.items.map { "\($0.reps) \($0.name.lowercased())" }.joined(separator: " · "))
                .foregroundStyle(.secondary)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
        }
    }

    // Écran de résultat + ressenti
    private func resultView(_ r: DefiRecord) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 6) {
                Text(clock(r.time, tenths: true))
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(isPB(r) ? .green : .primary)
                if let pb = previousBest {
                    Text(isPB(r) ? "Nouveau record ! −\(clock(pb.time - r.time))" : "+\(clock(r.time - pb.time)) sur ton record")
                        .font(.footnote)
                } else {
                    Text("Référence enregistrée").font(.footnote)
                }
                ForEach(Array(r.splits.enumerated()), id: \.offset) { i, s in
                    let prev = i == 0 ? 0 : r.splits[i - 1]
                    HStack { Text("Tour \(i + 1)"); Spacer(); Text(clock(s - prev)) }
                        .font(.footnote)
                }
                Text(feelGiven ? "Ressenti enregistré ✓" : "Ressenti ?")
                    .font(.headline).padding(.top, 4)
                if !feelGiven {
                    ForEach(feelLabels) { f in
                        Button("\(f.emoji) \(f.label)") {
                            store.setLastFeel(defi.id, level, f.id)
                            feelGiven = true
                        }
                    }
                }
                Button("Fermer") { onClose() }
                    .foregroundStyle(.green)
                    .padding(.top, 4)
            }
        }
    }

    private func isPB(_ r: DefiRecord) -> Bool {
        previousBest.map { r.time < $0.time } ?? true
    }

    private func lap(at t: Double) {
        guard isRunning else { return }
        splits.append(t)
        if splits.count >= rounds {
            finish(at: t)
        } else {
            WKInterfaceDevice.current().play(.click)
        }
    }

    private func togglePause() {
        if let s = startDate {
            accumulated += Date().timeIntervalSince(s)
            startDate = nil
            workout.pause()
            WKInterfaceDevice.current().play(.stop)
        } else {
            startDate = Date()
            workout.resume()
            WKInterfaceDevice.current().play(.start)
        }
    }

    private func finish(at t: Double) {
        finished = true
        startDate = nil
        accumulated = t
        let r = DefiRecord(date: Date(), time: t, splits: splits, feel: nil)
        store.add(defi.id, level, r)
        result = r
        WKInterfaceDevice.current().play(isPB(r) ? .notification : .success)
        Task { await workout.end() }
    }

    private func quit() {
        Task {
            await workout.end()
            onClose()
        }
    }
}
