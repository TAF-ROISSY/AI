import SwiftUI
import HealthKit

@main
struct FouleeWatchApp: App {
    @StateObject private var engine = TimerEngine()
    @StateObject private var workout = WorkoutManager()
    @StateObject private var defiStore = DefiStore()
    @StateObject private var figStore = FigStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(engine)
                .environmentObject(workout)
                .environmentObject(defiStore)
                .environmentObject(figStore)
        }
    }
}

/// Séances préréglées, alignées sur le plan de l'appli Foulée (iPhone/iPad).
struct Preset: Identifiable {
    let id = UUID()
    let name: String
    let mode: TimerMode
    let config: TimerConfig
    let running: Bool
}

let presets: [Preset] = [
    Preset(name: "Côtes 10 × 30 s", mode: .interval, config: TimerConfig(work: 30, rest: 90, rounds: 10), running: true),
    Preset(name: "VMA 8 × 400 m (≈1'40)", mode: .interval, config: TimerConfig(work: 100, rest: 75, rounds: 8), running: true),
    Preset(name: "Seuil 3 × 10 min", mode: .interval, config: TimerConfig(work: 600, rest: 120, rounds: 3), running: true),
    Preset(name: "Renfo · séries 45/75", mode: .interval, config: TimerConfig(work: 45, rest: 75, rounds: 19), running: false),
    Preset(name: "Circuit 40/20", mode: .interval, config: TimerConfig(work: 40, rest: 20, rounds: 20), running: false),
    Preset(name: "EMOM 20 min", mode: .emom, config: TimerConfig(minutes: 20), running: false),
    Preset(name: "AMRAP 15 min", mode: .amrap, config: TimerConfig(minutes: 15), running: false),
    Preset(name: "Abdos express 10 min", mode: .interval, config: TimerConfig(work: 40, rest: 20, rounds: 10), running: false)
]

struct ContentView: View {
    @EnvironmentObject var engine: TimerEngine
    @State private var path: [Route] = []

    enum Route: Hashable {
        case config(TimerMode)
        case run(isRunning: Bool, label: String)
    }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section("🏃 Trail") {
                    ForEach(presets.filter { $0.running }) { p in
                        Button {
                            engine.configure(mode: p.mode, config: p.config)
                            path.append(.run(isRunning: true, label: p.name))
                        } label: {
                            Label(p.name, systemImage: "figure.run")
                        }
                        .foregroundStyle(Color(red: 0.78, green: 0.96, blue: 0.2))
                    }
                }
                Section("🏋️ Muscu") {
                    NavigationLink {
                        DefiListView()
                    } label: {
                        Label("Défis Sommets", systemImage: "mountain.2.fill")
                    }
                    .foregroundStyle(.orange)
                    NavigationLink {
                        FigListView()
                    } label: {
                        Label("Figures", systemImage: "figure.gymnastics")
                    }
                    .foregroundStyle(.orange)
                    ForEach(presets.filter { !$0.running }) { p in
                        Button {
                            engine.configure(mode: p.mode, config: p.config)
                            path.append(.run(isRunning: false, label: p.name))
                        } label: {
                            Label(p.name, systemImage: "dumbbell.fill")
                        }
                        .foregroundStyle(.orange)
                    }
                }
                Section("Minuteur libre") {
                    ForEach(TimerMode.allCases) { m in
                        NavigationLink(value: Route.config(m)) {
                            Label(m.rawValue, systemImage: icon(m))
                        }
                    }
                }
            }
            .navigationTitle("Foulée")
            .navigationDestination(for: Route.self) { r in
                switch r {
                case .config(let m):
                    ConfigView(mode: m) { running in
                        path.append(.run(isRunning: running, label: m.rawValue))
                    }
                case .run(let running, _):
                    TimerView(activity: running ? .running : .functionalStrengthTraining) {
                        path.removeAll()
                    }
                }
            }
        }
    }

    private func icon(_ m: TimerMode) -> String {
        switch m {
        case .interval: return "repeat"
        case .emom: return "clock.arrow.circlepath"
        case .tabata: return "flame.fill"
        case .amrap: return "infinity"
        case .stopwatch: return "stopwatch"
        }
    }
}

struct ConfigView: View {
    let mode: TimerMode
    let onStart: (Bool) -> Void
    @EnvironmentObject var engine: TimerEngine
    @State private var cfg = TimerConfig()
    @State private var isRun = false

    var body: some View {
        Form {
            switch mode {
            case .interval:
                Stepper("Effort \(cfg.work) s", value: $cfg.work, in: 5...900, step: 5)
                Stepper("Récup \(cfg.rest) s", value: $cfg.rest, in: 0...600, step: 5)
                Stepper("× \(cfg.rounds)", value: $cfg.rounds, in: 1...50)
            case .emom, .amrap:
                Stepper("\(cfg.minutes) min", value: $cfg.minutes, in: 1...60)
            case .tabata:
                Text("20 s / 10 s × 8")
            case .stopwatch:
                EmptyView()
            }
            if mode != .stopwatch {
                Stepper("Prépa \(cfg.prep) s", value: $cfg.prep, in: 0...30, step: 5)
            }
            Toggle("Course à pied", isOn: $isRun)
            Button("Démarrer") {
                engine.configure(mode: mode, config: cfg)
                onStart(isRun)
            }
            .foregroundStyle(.green)
        }
        .navigationTitle(mode.rawValue)
    }
}

struct TimerView: View {
    let activity: HKWorkoutActivityType
    let onClose: () -> Void
    @EnvironmentObject var engine: TimerEngine
    @EnvironmentObject var workout: WorkoutManager
    @State private var started = false

    private var color: Color {
        if engine.isFinished { return .green }
        switch engine.current?.kind {
        case .rest: return .cyan
        case .prep: return .orange
        default: return Color(red: 0.78, green: 0.96, blue: 0.2)
        }
    }

    private var timeString: String {
        let t = engine.mode == .stopwatch ? engine.elapsed : engine.remaining
        let s = engine.mode == .stopwatch ? Int(t) : Int(ceil(t))
        return String(format: "%02d:%02d", s / 60, s % 60)
    }

    private var progress: Double {
        guard engine.mode != .stopwatch, let p = engine.current, p.duration > 0 else {
            return engine.isFinished ? 1 : 0
        }
        return 1 - engine.remaining / p.duration
    }

    var body: some View {
        VStack(spacing: 2) {
            HStack {
                Text(engine.isFinished ? "Terminé 💪" : (engine.current?.label ?? "Chrono"))
                    .font(.headline)
                    .foregroundStyle(color)
                Spacer()
                Text(engine.roundText).font(.footnote).foregroundStyle(.secondary)
            }
            ZStack {
                Circle().stroke(Color.gray.opacity(0.3), lineWidth: 6)
                Circle().trim(from: 0, to: progress)
                    .stroke(color, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text(timeString)
                    .font(.system(size: 40, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .minimumScaleFactor(0.6)
            }
            .padding(.vertical, 2)
            HStack {
                Label("\(Int(workout.heartRate))", systemImage: "heart.fill")
                    .foregroundStyle(.red)
                Spacer()
                Text("\(Int(workout.activeEnergy)) kcal").foregroundStyle(.secondary)
            }
            .font(.footnote)
            HStack(spacing: 6) {
                if !engine.isFinished {
                    Button {
                        if engine.isRunning { engine.pause(); workout.pause() }
                        else { engine.start(); workout.resume() }
                    } label: {
                        Image(systemName: engine.isRunning ? "pause.fill" : "play.fill")
                    }
                    .tint(color)
                }
                if engine.mode == .stopwatch && engine.isRunning {
                    Button { engine.lap() } label: { Image(systemName: "flag.fill") }
                }
                Button(role: .destructive) {
                    engine.reset()
                    Task {
                        await workout.end()
                        onClose()
                    }
                } label: {
                    Image(systemName: "xmark")
                }
            }
        }
        .padding(.horizontal, 4)
        .navigationBarBackButtonHidden(true)
        .task {
            guard !started else { return }
            started = true
            await workout.requestAuthorization()
            await workout.start(activity: activity)
            engine.start()
        }
    }
}
