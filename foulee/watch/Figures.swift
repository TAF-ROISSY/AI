import SwiftUI
import WatchKit
import Combine

// MARK: - Figures de callisthénie (mêmes parcours que l'onglet Figures de l'appli Foulée)

struct FigStep: Hashable {
    let name: String
    let cue: String
    let hold: Bool      // true : maintien en secondes, false : répétitions
    let target: Int
    let sets: Int
    let unit: String    // ex. "/côté"

    var targetText: String { hold ? "\(sets) × \(target) s" : "\(sets) × \(target)\(unit)" }
}

struct FigTree: Identifiable, Hashable {
    let id: String
    let name: String
    let icon: String
    let needsBar: Bool
    let steps: [FigStep]
}

/// Étape en cours de chaque parcours, gardée sur la montre.
final class FigStore: ObservableObject {
    @Published private(set) var steps: [String: Int]
    private let key = "fig.steps"

    init() {
        steps = (UserDefaults.standard.dictionary(forKey: key) as? [String: Int]) ?? [:]
    }

    func step(_ t: FigTree) -> Int { min(steps[t.id] ?? 0, t.steps.count - 1) }

    func set(_ t: FigTree, _ i: Int) {
        steps[t.id] = max(0, min(t.steps.count - 1, i))
        UserDefaults.standard.set(steps, forKey: key)
    }
}

let figTrees: [FigTree] = [
    FigTree(id: "pushup", name: "Pompe sur un bras", icon: "💪", needsBar: false, steps: [
        FigStep(name: "Pompes inclinées", cue: "Mains sur une table, corps gainé, poitrine jusqu’au bord.", hold: false, target: 12, sets: 3, unit: ""),
        FigStep(name: "Pompes classiques", cue: "Coudes à 45°, poitrine au sol, fessiers serrés.", hold: false, target: 12, sets: 3, unit: ""),
        FigStep(name: "Pompes déclinées", cue: "Pieds sur une chaise, même gainage.", hold: false, target: 12, sets: 3, unit: ""),
        FigStep(name: "Pompes diamant", cue: "Mains en losange sous la poitrine, coudes près du corps.", hold: false, target: 10, sets: 3, unit: ""),
        FigStep(name: "Pompes archer", cue: "Un bras fléchit, l’autre reste tendu sur le côté ; alterne.", hold: false, target: 6, sets: 3, unit: "/côté"),
        FigStep(name: "Pompe un bras inclinée", cue: "Main sur une table, pieds écartés, bassin parallèle au sol.", hold: false, target: 5, sets: 3, unit: "/côté"),
        FigStep(name: "Pompe sur un bras", cue: "Au sol, pieds écartés, descente contrôlée en 3 s.", hold: false, target: 3, sets: 3, unit: "/côté")
    ]),
    FigTree(id: "pullup", name: "Tractions", icon: "🧗", needsBar: true, steps: [
        FigStep(name: "Suspension active", cue: "Bras tendus, épaules tirées vers le bas, corps gainé.", hold: true, target: 30, sets: 3, unit: ""),
        FigStep(name: "Tractions scapulaires", cue: "Bras tendus, monte de 3 à 5 cm en serrant les omoplates.", hold: false, target: 10, sets: 3, unit: ""),
        FigStep(name: "Tractions négatives", cue: "Saute menton au-dessus de la barre, descends en 5 s.", hold: false, target: 5, sets: 3, unit: ""),
        FigStep(name: "Tractions assistées", cue: "Élastique sous les pieds ou un pied sur une chaise.", hold: false, target: 8, sets: 3, unit: ""),
        FigStep(name: "Tractions strictes", cue: "Départ bras tendus, menton au-dessus, sans élan.", hold: false, target: 5, sets: 3, unit: ""),
        FigStep(name: "10 tractions", cue: "Même exigence, rythme régulier.", hold: false, target: 10, sets: 3, unit: ""),
        FigStep(name: "Tractions archer", cue: "Tire vers une main, l’autre bras reste presque tendu.", hold: false, target: 4, sets: 3, unit: "/côté")
    ]),
    FigTree(id: "dips", name: "Dips", icon: "🪑", needsBar: false, steps: [
        FigStep(name: "Dips sur banc", cue: "Mains sur une chaise derrière toi, jambes fléchies.", hold: false, target: 12, sets: 3, unit: ""),
        FigStep(name: "Dips banc jambes tendues", cue: "Talons au sol loin devant, coudes vers l’arrière.", hold: false, target: 12, sets: 3, unit: ""),
        FigStep(name: "Dips négatifs entre deux chaises", cue: "Descente en 4 s, épaules basses.", hold: false, target: 5, sets: 3, unit: ""),
        FigStep(name: "Dips entre deux chaises", cue: "Jusqu’à 90° aux coudes, buste légèrement penché.", hold: false, target: 8, sets: 3, unit: ""),
        FigStep(name: "15 dips", cue: "Contrôle total, pas de rebond en bas.", hold: false, target: 15, sets: 3, unit: "")
    ]),
    FigTree(id: "hspu", name: "Pompe en équilibre", icon: "🙃", needsBar: false, steps: [
        FigStep(name: "Pompes piquées", cue: "Bassin haut, tête vers le sol entre les mains.", hold: false, target: 10, sets: 3, unit: ""),
        FigStep(name: "Pompes piquées pieds surélevés", cue: "Pieds sur une chaise, buste vertical.", hold: false, target: 8, sets: 3, unit: ""),
        FigStep(name: "Négatifs au mur", cue: "En équilibre au mur, descente en 4 s, tête sur un coussin.", hold: false, target: 4, sets: 3, unit: ""),
        FigStep(name: "Pompe en équilibre au mur", cue: "Descente et remontée complètes.", hold: false, target: 5, sets: 3, unit: "")
    ]),
    FigTree(id: "pistol", name: "Pistol squat", icon: "🦵", needsBar: false, steps: [
        FigStep(name: "Squats profonds", cue: "Talons au sol, hanches sous les genoux.", hold: false, target: 20, sets: 3, unit: ""),
        FigStep(name: "Fentes bulgares", cue: "Pied arrière sur une chaise.", hold: false, target: 10, sets: 3, unit: "/jambe"),
        FigStep(name: "Step-down", cue: "Debout sur une marche, pose le talon libre au sol en 3 s.", hold: false, target: 8, sets: 3, unit: "/jambe"),
        FigStep(name: "Pistol assisté", cue: "Tiens un montant de porte, descends le plus bas possible.", hold: false, target: 6, sets: 3, unit: "/jambe"),
        FigStep(name: "Pistol sur une chaise", cue: "Descends t’asseoir sur une chaise, remonte sans élan.", hold: false, target: 5, sets: 3, unit: "/jambe"),
        FigStep(name: "Pistol squat", cue: "Bras devant, jambe libre tendue, talon au sol.", hold: false, target: 5, sets: 3, unit: "/jambe")
    ]),
    FigTree(id: "nordic", name: "Nordic curl", icon: "⛰️", needsBar: false, steps: [
        FigStep(name: "Pont fessier 1 jambe", cue: "Monte le bassin, 1 s en haut.", hold: false, target: 12, sets: 3, unit: "/jambe"),
        FigStep(name: "Glissés ischios", cue: "Dos au sol, talons sur une serviette, ramène et éloigne les pieds.", hold: false, target: 10, sets: 3, unit: ""),
        FigStep(name: "Nordic négatif amorti", cue: "À genoux, pieds bloqués sous un canapé, descends en 3 s et rattrape-toi avec les mains.", hold: false, target: 5, sets: 3, unit: ""),
        FigStep(name: "Nordic négatif lent", cue: "Descente en 5 s, le plus bas possible.", hold: false, target: 5, sets: 3, unit: ""),
        FigStep(name: "Nordic curl", cue: "Descente contrôlée, remontée avec une petite poussée des mains.", hold: false, target: 5, sets: 3, unit: "")
    ]),
    FigTree(id: "core", name: "Dragon flag", icon: "🐉", needsBar: false, steps: [
        FigStep(name: "Hollow hold", cue: "Bas du dos plaqué, bras et jambes tendus.", hold: true, target: 30, sets: 3, unit: ""),
        FigStep(name: "Relevés de jambes tendues", cue: "Sans toucher le sol en bas.", hold: false, target: 12, sets: 3, unit: ""),
        FigStep(name: "Dragon flag groupé", cue: "Allongé sur un banc, mains agrippées derrière la tête, monte le corps genoux pliés.", hold: false, target: 5, sets: 3, unit: ""),
        FigStep(name: "Dragon flag négatif", cue: "Corps tendu, descente en 5 s.", hold: false, target: 4, sets: 3, unit: ""),
        FigStep(name: "Dragon flag", cue: "Corps rigide, montée et descente contrôlées.", hold: false, target: 5, sets: 3, unit: "")
    ]),
    FigTree(id: "lsit", name: "L-sit", icon: "🔺", needsBar: false, steps: [
        FigStep(name: "Appui bras tendus", cue: "Mains sur deux chaises, épaules basses, corps décollé.", hold: true, target: 20, sets: 3, unit: ""),
        FigStep(name: "Tuck L-sit", cue: "Genoux ramenés à la poitrine, en appui.", hold: true, target: 10, sets: 3, unit: ""),
        FigStep(name: "L-sit une jambe", cue: "Une jambe tendue, l’autre repliée ; alterne.", hold: true, target: 10, sets: 3, unit: ""),
        FigStep(name: "L-sit", cue: "Jambes tendues à l’horizontale, pointes tendues.", hold: true, target: 10, sets: 3, unit: ""),
        FigStep(name: "L-sit 20 s", cue: "Même position, respiration calme.", hold: true, target: 20, sets: 3, unit: "")
    ]),
    FigTree(id: "hs", name: "Équilibre sur les mains", icon: "🤸", needsBar: false, steps: [
        FigStep(name: "Planche haute", cue: "Bras tendus, épaules au-dessus des mains.", hold: true, target: 30, sets: 3, unit: ""),
        FigStep(name: "Pike hold", cue: "Bassin haut, poids sur les mains, regard entre les mains.", hold: true, target: 20, sets: 3, unit: ""),
        FigStep(name: "Marche au mur", cue: "Pieds au mur, remonte jusqu’à avoir le ventre près du mur.", hold: true, target: 20, sets: 3, unit: ""),
        FigStep(name: "Handstand ventre au mur", cue: "Corps aligné, ventre contre le mur, pousse dans le sol.", hold: true, target: 45, sets: 3, unit: ""),
        FigStep(name: "Kick-up et décollés", cue: "Monte face au mur, décolle les pieds quelques secondes.", hold: false, target: 10, sets: 1, unit: " essais"),
        FigStep(name: "Handstand libre", cue: "Sans mur, corrige avec les doigts.", hold: true, target: 10, sets: 3, unit: ""),
        FigStep(name: "Handstand 30 s", cue: "Libre, aligné, sans pas.", hold: true, target: 30, sets: 2, unit: "")
    ]),
    FigTree(id: "planche", name: "Planche", icon: "🛫", needsBar: false, steps: [
        FigStep(name: "Planche lean", cue: "Planche haute, avance les épaules au-delà des mains.", hold: true, target: 20, sets: 3, unit: ""),
        FigStep(name: "Frog stand", cue: "Genoux posés sur les coudes, pieds décollés.", hold: true, target: 20, sets: 3, unit: ""),
        FigStep(name: "Tuck planche", cue: "Genoux à la poitrine, bassin à hauteur des épaules.", hold: true, target: 10, sets: 3, unit: ""),
        FigStep(name: "Tuck planche avancée", cue: "Dos plat, hanches ouvertes.", hold: true, target: 8, sets: 3, unit: ""),
        FigStep(name: "Straddle planche", cue: "Jambes écartées et tendues.", hold: true, target: 5, sets: 3, unit: "")
    ]),
    FigTree(id: "fl", name: "Front lever", icon: "➖", needsBar: true, steps: [
        FigStep(name: "Suspension active", cue: "Épaules basses, corps gainé.", hold: true, target: 30, sets: 3, unit: ""),
        FigStep(name: "Tuck front lever", cue: "Genoux à la poitrine, dos à l’horizontale.", hold: true, target: 10, sets: 3, unit: ""),
        FigStep(name: "Tuck avancé", cue: "Dos plat, hanches ouvertes à 90°.", hold: true, target: 10, sets: 3, unit: ""),
        FigStep(name: "Front lever une jambe", cue: "Une jambe tendue.", hold: true, target: 8, sets: 3, unit: ""),
        FigStep(name: "Front lever", cue: "Corps entier à l’horizontale.", hold: true, target: 5, sets: 3, unit: "")
    ]),
    FigTree(id: "mu", name: "Muscle-up", icon: "🚀", needsBar: true, steps: [
        FigStep(name: "10 tractions strictes", cue: "Base indispensable.", hold: false, target: 10, sets: 3, unit: ""),
        FigStep(name: "Tractions poitrine à la barre", cue: "Tire jusqu’à toucher la barre avec le haut de la poitrine.", hold: false, target: 5, sets: 3, unit: ""),
        FigStep(name: "Tractions explosives", cue: "Le plus haut possible, mains qui lâchent presque.", hold: false, target: 4, sets: 3, unit: ""),
        FigStep(name: "Transition négative", cue: "Pars au-dessus de la barre et redescends lentement par la transition.", hold: false, target: 4, sets: 3, unit: ""),
        FigStep(name: "Muscle-up", cue: "Traction explosive, poitrine par-dessus, poussée finale.", hold: false, target: 2, sets: 3, unit: "")
    ])
]

// MARK: - Vues

struct FigListView: View {
    @EnvironmentObject var store: FigStore

    var body: some View {
        List(figTrees) { t in
            NavigationLink {
                FigDetailView(tree: t)
            } label: {
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(t.icon) \(t.name)").font(.headline)
                    Text("Étape \(store.step(t) + 1)/\(t.steps.count) · \(t.steps[store.step(t)].name)")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
        .navigationTitle("Figures")
    }
}

struct FigDetailView: View {
    let tree: FigTree
    @EnvironmentObject var store: FigStore

    var body: some View {
        let i = store.step(tree)
        let s = tree.steps[i]
        ScrollView {
            VStack(alignment: .leading, spacing: 6) {
                Text("Étape \(i + 1)/\(tree.steps.count)").font(.footnote).foregroundStyle(.secondary)
                Text(s.name).font(.headline)
                Text(s.targetText).font(.title3.bold()).foregroundStyle(.orange)
                Text(s.cue).font(.footnote)
                if tree.needsBar {
                    Text("Barre ou anneaux").font(.caption2).foregroundStyle(.secondary)
                }
                NavigationLink {
                    FigRunView(tree: tree, index: i)
                } label: {
                    Label("Démarrer", systemImage: "play.fill")
                }
                .tint(.orange)
                HStack {
                    Button {
                        store.set(tree, i - 1)
                    } label: { Image(systemName: "chevron.left") }
                    .disabled(i == 0)
                    Button {
                        store.set(tree, i + 1)
                    } label: { Image(systemName: "chevron.right") }
                    .disabled(i == tree.steps.count - 1)
                }
                Text("Les flèches changent d'étape. Pense à noter tes séries dans l'appli sur l'iPhone.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("\(tree.icon) \(tree.name)")
    }
}

struct FigRunView: View {
    let tree: FigTree
    let index: Int
    @EnvironmentObject var store: FigStore
    @Environment(\.dismiss) private var dismiss

    enum Phase { case prep, work, rest, done }

    @State private var phase: Phase = .prep
    @State private var current = 0
    @State private var phaseStart = Date()
    @State private var now = Date()
    @State private var results: [Int] = []

    private let prepTime: Double = 5
    private let restTime: Double = 90
    private let tick = Timer.publish(every: 0.2, on: .main, in: .common).autoconnect()

    private var step: FigStep { tree.steps[index] }
    private var elapsed: Double { now.timeIntervalSince(phaseStart) }
    private var reached: Bool { results.count == step.sets && results.allSatisfy { $0 >= step.target } }

    var body: some View {
        VStack(spacing: 4) {
            switch phase {
            case .prep:
                Text("Série \(current + 1)/\(step.sets)").font(.headline)
                Text(step.name).font(.footnote).multilineTextAlignment(.center).lineLimit(2)
                Text("\(Int(ceil(max(0, prepTime - elapsed))))")
                    .font(.system(size: 46, weight: .bold, design: .rounded))
                    .foregroundStyle(.orange)
            case .work:
                Text("Série \(current + 1)/\(step.sets)").font(.headline)
                if step.hold {
                    Text("\(Int(elapsed)) s")
                        .font(.system(size: 46, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(elapsed >= Double(step.target) ? .green : .orange)
                    Text("objectif \(step.target) s").font(.footnote).foregroundStyle(.secondary)
                    Button("Lâché") { endSet(Int(elapsed)) }.tint(.orange)
                } else {
                    Text("\(step.target)\(step.unit)")
                        .font(.system(size: 40, weight: .bold, design: .rounded))
                        .foregroundStyle(.orange)
                    Text(step.name).font(.footnote).lineLimit(2)
                    Button("Série faite") { endSet(step.target) }.tint(.orange)
                }
            case .rest:
                Text("Repos").font(.headline).foregroundStyle(.cyan)
                Text("\(Int(ceil(max(0, restTime - elapsed))))")
                    .font(.system(size: 46, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.cyan)
                Text("Ensuite : série \(current + 1)/\(step.sets)").font(.footnote)
                Button("Passer") { begin(.prep) }
            case .done:
                Text(reached ? "Objectif atteint 💪" : "Séance terminée").font(.headline)
                Text(results.map { step.hold ? "\($0) s" : "\($0)" }.joined(separator: " · "))
                    .font(.footnote)
                if reached && index < tree.steps.count - 1 {
                    Text("Valide l'étape quand tu as réussi 2 séances.").font(.caption2).foregroundStyle(.secondary)
                    Button("Étape suivante ›") {
                        store.set(tree, index + 1)
                        dismiss()
                    }
                    .tint(.green)
                }
                Button("Terminer") { dismiss() }
            }
        }
        .navigationBarBackButtonHidden(phase != .done)
        .onAppear {
            phaseStart = Date()
            WKInterfaceDevice.current().play(.click)
        }
        .onReceive(tick) { d in
            now = d
            advance()
        }
    }

    private func begin(_ p: Phase) {
        phase = p
        phaseStart = Date()
        now = phaseStart
    }

    private func advance() {
        switch phase {
        case .prep:
            if elapsed >= prepTime {
                begin(.work)
                WKInterfaceDevice.current().play(.start)
            }
        case .work:
            // Signal discret quand l'objectif de maintien est atteint (on peut continuer).
            if step.hold && Int(elapsed) == step.target && elapsed - Double(step.target) < 0.2 {
                WKInterfaceDevice.current().play(.success)
            }
        case .rest:
            if elapsed >= restTime - 3 && elapsed < restTime - 2.8 {
                WKInterfaceDevice.current().play(.click)
            }
            if elapsed >= restTime { begin(.prep) }
        case .done:
            break
        }
    }

    private func endSet(_ value: Int) {
        results.append(value)
        if current + 1 >= step.sets {
            begin(.done)
            WKInterfaceDevice.current().play(reached ? .success : .stop)
        } else {
            current += 1
            begin(.rest)
            WKInterfaceDevice.current().play(.stop)
        }
    }
}
