import SwiftUI
import WatchKit
import HealthKit

// MARK: - Modèle (généré depuis les données de l'appli Foulée iPhone/iPad : mêmes défis, mêmes répétitions)

enum DefiCat: String, CaseIterable {
    case sommet, cardio, haut, core, bas, endu
    var label: String {
        switch self {
        case .sommet: return "⛰️ Sommets"
        case .cardio: return "🔥 Cardio"
        case .haut: return "💪 Haut du corps"
        case .core: return "🧱 Abdos & core"
        case .bas: return "🦵 Bas du corps"
        case .endu: return "♾️ Endurance"
        }
    }
}

struct DefiItem: Hashable {
    let name: String
    let reps: Int
    let unit: String   // "" = répétitions, "m" = mètres
}

struct Defi: Identifiable, Hashable {
    let id: String
    let name: String
    let cat: DefiCat
    let detail: String
    let alt: Int
    let items: [DefiItem]
    let levels: [Int]      // nombre de tours (ou de paliers) par niveau
    let ladder: [Int]?     // paliers type 50-40-30-20-10
    let scale: [Double]    // coefficient de volume par niveau
    let scaled: Bool       // true : les répétitions suivent le coefficient du niveau
    let rest: Int          // repos imposé entre les tours, en secondes

    func rounds(_ lv: Int) -> Int { levels[min(lv, levels.count - 1)] }

    /// Quantité d'un exercice pour un tour donné et un niveau donné.
    func qty(_ it: DefiItem, level lv: Int, round k: Int) -> Int {
        let f = scale[min(lv, scale.count - 1)]
        if let l = ladder { return max(1, Int((Double(l[min(k, l.count - 1)]) * f).rounded())) }
        return scaled ? max(1, Int((Double(it.reps) * f).rounded())) : it.reps
    }

    func line(_ it: DefiItem, level lv: Int, round k: Int) -> String {
        let q = qty(it, level: lv, round: k)
        return it.unit.isEmpty ? "\(q) \(it.name.lowercased())" : "\(q) \(it.unit) \(it.name.lowercased())"
    }

    func levelLabel(_ i: Int) -> String {
        if let l = ladder { return "\(levelNames[i]) · " + l.prefix(3).map { "\(max(1, Int((Double($0) * scale[i]).rounded())))" }.joined(separator: "-") + "…" }
        if scaled { return "\(levelNames[i]) · \(Int(scale[i] * 100)) %" }
        return "\(levelNames[i]) · \(levels[i]) tours"
    }
}

let levelNames = ["Base", "★", "★★"]
struct Feel: Identifiable { let id: Int; let emoji: String; let label: String }
let feelLabels = [Feel(id: 1, emoji: "😎", label: "Trop facile"), Feel(id: 2, emoji: "👌", label: "Parfait"),
                  Feel(id: 3, emoji: "😤", label: "Difficile"), Feel(id: 4, emoji: "🥵", label: "Trop dur")]

let defis: [Defi] = [
    Defi(id: "ventoux", name: "Ventoux", cat: .sommet, detail: "Le classique pour débuter : court et complet.", alt: 1910,
         items: [.init(name: "Swing 2 mains", reps: 15, unit: ""), .init(name: "Goblet squat", reps: 10, unit: ""), .init(name: "Pompes", reps: 10, unit: ""), .init(name: "Mountain climbers", reps: 20, unit: "")],
         levels: [3, 4, 5], ladder: nil, scale: [1, 1, 1], scaled: false, rest: 0),
    Defi(id: "puy", name: "Puy de Dôme", cat: .sommet, detail: "Sans matériel : parfait en voyage ou à l’hôtel.", alt: 1465,
         items: [.init(name: "Burpees", reps: 10, unit: ""), .init(name: "Fentes alternées", reps: 20, unit: ""), .init(name: "Dead bug", reps: 20, unit: ""), .init(name: "Pompes", reps: 10, unit: "")],
         levels: [3, 4, 5], ladder: nil, scale: [1, 1, 1], scaled: false, rest: 0),
    Defi(id: "aneto", name: "Aneto", cat: .sommet, detail: "Jambes de trailer : tout pour les montées.", alt: 3404,
         items: [.init(name: "Swing 2 mains", reps: 20, unit: ""), .init(name: "Goblet squat", reps: 15, unit: ""), .init(name: "Fente bulgare", reps: 10, unit: ""), .init(name: "Mollets excentriques", reps: 20, unit: "")],
         levels: [3, 4, 5], ladder: nil, scale: [1, 1, 1], scaled: false, rest: 0),
    Defi(id: "etna", name: "Etna", cat: .sommet, detail: "Haut du corps et sangle abdominale en feu.", alt: 3357,
         items: [.init(name: "Pompes", reps: 12, unit: ""), .init(name: "Rowing KB 1 bras", reps: 20, unit: ""), .init(name: "Épaulé + développé (clean & press)", reps: 10, unit: ""), .init(name: "Roue abdo à genoux", reps: 10, unit: "")],
         levels: [3, 4, 5], ladder: nil, scale: [1, 1, 1], scaled: false, rest: 0),
    Defi(id: "blanc", name: "Mont Blanc", cat: .sommet, detail: "Le grand full body. Gère ton allure dès le 1er tour.", alt: 4806,
         items: [.init(name: "Swing 2 mains", reps: 20, unit: ""), .init(name: "Thruster goblet", reps: 12, unit: ""), .init(name: "Burpees", reps: 10, unit: ""), .init(name: "Rowing KB 1 bras", reps: 16, unit: ""), .init(name: "Roue abdo", reps: 10, unit: "")],
         levels: [3, 4, 5], ladder: nil, scale: [1, 1, 1], scaled: false, rest: 0),
    Defi(id: "annapurna", name: "Annapurna", cat: .sommet, detail: "Échelle 50-40-30-20-10 façon « Aphrodite » : à chaque palier, les 3 exercices.", alt: 8091,
         items: [.init(name: "Swing 2 mains", reps: 0, unit: ""), .init(name: "Squat poids du corps", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: "")],
         levels: [5, 5, 5], ladder: [50, 40, 30, 20, 10], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "cervin", name: "Cervin", cat: .sommet, detail: "Pyramide descendante 10 → 1 : pompes + goblet squats. Silencieux.", alt: 4478,
         items: [.init(name: "Pompes", reps: 0, unit: ""), .init(name: "Goblet squat", reps: 0, unit: "")],
         levels: [10, 10, 10], ladder: [10, 9, 8, 7, 6, 5, 4, 3, 2, 1], scale: [0.6, 0.8, 1], scaled: true, rest: 0),
    Defi(id: "kili", name: "Kilimandjaro", cat: .sommet, detail: "L’ultra : long et régulier. Après 4 semaines de plan minimum.", alt: 5895,
         items: [.init(name: "Swing 2 mains", reps: 25, unit: ""), .init(name: "Goblet squat", reps: 20, unit: ""), .init(name: "Pompes", reps: 15, unit: ""), .init(name: "Fentes alternées", reps: 20, unit: ""), .init(name: "Mountain climbers", reps: 30, unit: ""), .init(name: "Burpees", reps: 10, unit: "")],
         levels: [3, 4, 5], ladder: nil, scale: [1, 1, 1], scaled: false, rest: 0),
    Defi(id: "aphrodite", name: "Aphrodite", cat: .cardio, detail: "Le classique full body : paliers dégressifs, tout le corps brûle.", alt: 0,
         items: [.init(name: "Burpees", reps: 0, unit: ""), .init(name: "Squat poids du corps", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: "")],
         levels: [5, 5, 5], ladder: [50, 40, 30, 20, 10], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "metis", name: "Metis", cat: .cardio, detail: "Cardio express, très court et très intense.", alt: 0,
         items: [.init(name: "Burpees", reps: 0, unit: ""), .init(name: "Mountain climbers", reps: 0, unit: ""), .init(name: "Montées de genoux", reps: 0, unit: "")],
         levels: [3, 3, 3], ladder: [10, 25, 10], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hellas", name: "Hellas", cat: .cardio, detail: "Cardio et jambes en pyramide montante puis descendante.", alt: 0,
         items: [.init(name: "Burpees", reps: 0, unit: ""), .init(name: "Montées de genoux", reps: 0, unit: ""), .init(name: "Squat poids du corps", reps: 0, unit: ""), .init(name: "Jumping jacks", reps: 0, unit: "")],
         levels: [5, 5, 5], ladder: [10, 20, 30, 20, 10], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "dione", name: "Dione", cat: .cardio, detail: "Cardio et sangle : gros volume de jacks, burpees et gainage dynamique.", alt: 0,
         items: [.init(name: "Jumping jacks", reps: 75, unit: ""), .init(name: "Burpees", reps: 25, unit: ""), .init(name: "Relevés de jambes tendues", reps: 50, unit: ""), .init(name: "Jumping jacks", reps: 75, unit: ""), .init(name: "Sit-up", reps: 50, unit: ""), .init(name: "Burpees", reps: 25, unit: "")],
         levels: [3, 3, 3], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "iris", name: "Iris", cat: .cardio, detail: "Dix tours courts de course et de jacks : cœur et jambes.", alt: 0,
         items: [.init(name: "Course", reps: 100, unit: "m"), .init(name: "Jumping jacks", reps: 100, unit: "")],
         levels: [10, 10, 10], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "nyx", name: "Nyx", cat: .cardio, detail: "Court et nerveux : cardio et abdos.", alt: 0,
         items: [.init(name: "Montées de genoux", reps: 10, unit: ""), .init(name: "Burpees", reps: 10, unit: ""), .init(name: "Relevés de jambes tendues", reps: 10, unit: ""), .init(name: "Montées de genoux", reps: 10, unit: "")],
         levels: [3, 3, 3], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "kerberos", name: "Kerberos", cat: .cardio, detail: "Cardio extrême, 100 répétitions par tour.", alt: 0,
         items: [.init(name: "Burpees", reps: 25, unit: ""), .init(name: "Mountain climbers", reps: 25, unit: ""), .init(name: "Montées de genoux", reps: 25, unit: ""), .init(name: "Sauts groupés", reps: 25, unit: "")],
         levels: [3, 3, 3], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "eagle", name: "Eagle", cat: .cardio, detail: "Dix tours rapides : cardio et jambes.", alt: 0,
         items: [.init(name: "Burpees", reps: 10, unit: ""), .init(name: "Montées de genoux", reps: 10, unit: ""), .init(name: "Squat poids du corps", reps: 10, unit: "")],
         levels: [10, 10, 10], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "athena", name: "Athena", cat: .haut, detail: "Haut du corps et poussée en paliers dégressifs.", alt: 0,
         items: [.init(name: "Pompes", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: ""), .init(name: "Squat poids du corps", reps: 0, unit: "")],
         levels: [5, 5, 5], ladder: [25, 20, 15, 10, 5], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "kentauros", name: "Kentauros", cat: .bas, detail: "Jambes et explosivité sur la distance.", alt: 0,
         items: [.init(name: "Fentes marchées", reps: 40, unit: "m"), .init(name: "Montées de genoux", reps: 10, unit: ""), .init(name: "Burpee frogs", reps: 40, unit: "m"), .init(name: "Sauts groupés", reps: 10, unit: "")],
         levels: [6, 6, 6], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hera", name: "Hera", cat: .haut, detail: "Haut du corps et sangle : pompes et climbers en volume.", alt: 0,
         items: [.init(name: "Pompes", reps: 0, unit: ""), .init(name: "Mountain climbers", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: "")],
         levels: [5, 5, 5], ladder: [40, 30, 20, 10, 5], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "poseidon", name: "Poseidon", cat: .haut, detail: "Tirage et poussée en express.", alt: 0,
         items: [.init(name: "Tractions (ou rowing KB)", reps: 0, unit: ""), .init(name: "Pompes", reps: 0, unit: "")],
         levels: [5, 5, 5], ladder: [25, 20, 15, 10, 5], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "ares", name: "Ares", cat: .haut, detail: "Haut du corps et sprints.", alt: 0,
         items: [.init(name: "Tractions (ou rowing KB)", reps: 7, unit: ""), .init(name: "Pompes", reps: 7, unit: ""), .init(name: "Sprint", reps: 80, unit: "m")],
         levels: [5, 5, 5], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hephaistos", name: "Hephaistos", cat: .haut, detail: "Poussée et gainage dorsal et abdominal.", alt: 0,
         items: [.init(name: "Pompes", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: ""), .init(name: "Superman", reps: 0, unit: ""), .init(name: "Relevés de jambes tendues", reps: 0, unit: "")],
         levels: [4, 4, 4], ladder: [20, 15, 10, 5], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "cronos", name: "Cronos", cat: .haut, detail: "Gros volume haut et bas du corps, 250 répétitions par tour.", alt: 0,
         items: [.init(name: "Burpees", reps: 50, unit: ""), .init(name: "Squat poids du corps", reps: 50, unit: ""), .init(name: "Pompes", reps: 50, unit: ""), .init(name: "Sit-up", reps: 50, unit: ""), .init(name: "Relevés de jambes tendues", reps: 50, unit: "")],
         levels: [3, 3, 3], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hyperion", name: "Hyperion", cat: .haut, detail: "Force et endurance en montée progressive.", alt: 0,
         items: [.init(name: "Montées de genoux", reps: 6, unit: ""), .init(name: "Pompes", reps: 12, unit: ""), .init(name: "Squat poids du corps", reps: 18, unit: ""), .init(name: "Mountain climbers", reps: 24, unit: "")],
         levels: [5, 5, 5], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "zeus", name: "Zeus", cat: .haut, detail: "Force pure, 2 min de repos entre les tours.", alt: 0,
         items: [.init(name: "Pompes en équilibre (ou piquées)", reps: 5, unit: ""), .init(name: "Tractions (ou rowing KB)", reps: 15, unit: ""), .init(name: "Pompes", reps: 25, unit: ""), .init(name: "Sit-up", reps: 35, unit: ""), .init(name: "Squat poids du corps", reps: 45, unit: "")],
         levels: [4, 4, 4], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 120),
    Defi(id: "prometheus", name: "Prometheus", cat: .core, detail: "Sangle et full body en pyramide inversée.", alt: 0,
         items: [.init(name: "Mountain climbers", reps: 0, unit: ""), .init(name: "Pompes", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: ""), .init(name: "Squat poids du corps", reps: 0, unit: ""), .init(name: "Jumping jacks", reps: 0, unit: "")],
         levels: [5, 5, 5], ladder: [30, 20, 10, 20, 30], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hercules", name: "Hercules", cat: .core, detail: "Sangle et haut du corps, 250 répétitions par tour.", alt: 0,
         items: [.init(name: "Pompes", reps: 50, unit: ""), .init(name: "Sit-up", reps: 50, unit: ""), .init(name: "Squat poids du corps", reps: 50, unit: ""), .init(name: "Relevés de jambes tendues", reps: 50, unit: ""), .init(name: "Burpees", reps: 50, unit: "")],
         levels: [3, 3, 3], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "triton", name: "Triton", cat: .core, detail: "Sangle et jambes en paliers.", alt: 0,
         items: [.init(name: "Burpees", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: ""), .init(name: "Relevés de jambes tendues", reps: 0, unit: ""), .init(name: "Squat poids du corps", reps: 0, unit: "")],
         levels: [3, 3, 3], ladder: [30, 20, 10], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "apollon", name: "Apollon", cat: .core, detail: "Sangle et cardio avec deux courses par tour.", alt: 0,
         items: [.init(name: "Burpees", reps: 25, unit: ""), .init(name: "Course", reps: 400, unit: "m"), .init(name: "Squat poids du corps", reps: 50, unit: ""), .init(name: "Course", reps: 400, unit: "m")],
         levels: [3, 3, 3], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "morpheus", name: "Morpheus", cat: .core, detail: "Cardio doux, parfait pour un jour léger.", alt: 0,
         items: [.init(name: "Pompes", reps: 5, unit: ""), .init(name: "Fentes alternées", reps: 10, unit: ""), .init(name: "Jumping jacks", reps: 15, unit: "")],
         levels: [5, 5, 5], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "gaia", name: "Gaia", cat: .core, detail: "Volume sangle et jambes sur dix tours.", alt: 0,
         items: [.init(name: "Jumping jacks", reps: 10, unit: ""), .init(name: "Fentes alternées", reps: 10, unit: ""), .init(name: "Stand-ups", reps: 10, unit: "")],
         levels: [10, 10, 10], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hades", name: "Hades", cat: .bas, detail: "Jambes, sangle et poussée, avec un sprint final par tour.", alt: 0,
         items: [.init(name: "Burpees", reps: 25, unit: ""), .init(name: "Tractions (ou rowing KB)", reps: 15, unit: ""), .init(name: "Pompes", reps: 15, unit: ""), .init(name: "Burpees", reps: 25, unit: ""), .init(name: "Course", reps: 60, unit: "m")],
         levels: [3, 3, 3], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "artemis", name: "Artemis", cat: .bas, detail: "Endurance musculaire globale, un seul tour pour le chrono.", alt: 0,
         items: [.init(name: "Burpees", reps: 50, unit: ""), .init(name: "Tractions (ou rowing KB)", reps: 50, unit: ""), .init(name: "Pompes", reps: 100, unit: ""), .init(name: "Squat poids du corps", reps: 150, unit: ""), .init(name: "Burpees", reps: 50, unit: "")],
         levels: [1, 1, 1], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "persephone", name: "Persephone", cat: .bas, detail: "Jambes et cardio en paliers.", alt: 0,
         items: [.init(name: "Fentes alternées", reps: 0, unit: ""), .init(name: "Burpees", reps: 0, unit: ""), .init(name: "Relevés de jambes tendues", reps: 0, unit: "")],
         levels: [3, 3, 3], ladder: [30, 20, 10], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hermes", name: "Hermes", cat: .bas, detail: "Explosivité : pompes et sprints, 2 min de repos entre les tours.", alt: 0,
         items: [.init(name: "Pompes", reps: 10, unit: ""), .init(name: "Sprint", reps: 20, unit: "m"), .init(name: "Pompes", reps: 10, unit: ""), .init(name: "Sprint", reps: 20, unit: "m")],
         levels: [4, 4, 4], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 120),
    Defi(id: "odysseus", name: "Odysseus", cat: .bas, detail: "Endurance de force équilibrée.", alt: 0,
         items: [.init(name: "Montées de genoux", reps: 15, unit: ""), .init(name: "Pompes", reps: 15, unit: ""), .init(name: "Squat poids du corps", reps: 15, unit: ""), .init(name: "Sit-up", reps: 15, unit: "")],
         levels: [5, 5, 5], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "kronos", name: "Kronos", cat: .endu, detail: "L’ultra-endurance : 600 répétitions d’un seul tenant.", alt: 0,
         items: [.init(name: "Pompes", reps: 100, unit: ""), .init(name: "Sit-up", reps: 100, unit: ""), .init(name: "Squat poids du corps", reps: 100, unit: ""), .init(name: "Relevés de jambes tendues", reps: 100, unit: ""), .init(name: "Burpees", reps: 100, unit: ""), .init(name: "Tractions (ou rowing KB)", reps: 100, unit: "")],
         levels: [1, 1, 1], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "hestia", name: "Hestia", cat: .endu, detail: "Circuit rapide en paliers.", alt: 0,
         items: [.init(name: "Burpees", reps: 0, unit: ""), .init(name: "Montées de genoux", reps: 0, unit: ""), .init(name: "Sit-up", reps: 0, unit: "")],
         levels: [3, 3, 3], ladder: [20, 15, 10], scale: [0.5, 0.75, 1], scaled: true, rest: 0),
    Defi(id: "thanatos", name: "Thanatos", cat: .endu, detail: "Cardio et sangle variés, volume croissant par exercice.", alt: 0,
         items: [.init(name: "Burpees", reps: 10, unit: ""), .init(name: "Relevés de jambes tendues", reps: 20, unit: ""), .init(name: "Mountain climbers", reps: 30, unit: ""), .init(name: "Stand-ups", reps: 40, unit: ""), .init(name: "Montées de genoux", reps: 50, unit: "")],
         levels: [4, 4, 4], ladder: nil, scale: [0.5, 0.75, 1], scaled: true, rest: 0)
]

func clock(_ t: Double, tenths: Bool = false) -> String {
    let s = Int(max(0, t))
    let base = String(format: "%d:%02d", s / 60, s % 60)
    return tenths ? base + ".\(Int((max(0, t) - Double(s)) * 10))" : base
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
        List {
            ForEach(DefiCat.allCases, id: \.self) { cat in
                Section(cat.label) {
                    ForEach(defis.filter { $0.cat == cat }) { d in
                        NavigationLink {
                            DefiDetailView(defi: d)
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(d.name).font(.headline)
                                let lv = store.highestUnlocked(d)
                                if let b = store.best(d.id, lv) {
                                    Text("\(levelNames[lv]) · record \(clock(b.time))").font(.footnote).foregroundStyle(.secondary)
                                } else {
                                    Text(d.alt > 0 ? "\(d.alt) m · pas encore tenté" : "Pas encore tenté").font(.footnote).foregroundStyle(.secondary)
                                }
                            }
                        }
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
            Text(defi.detail).font(.footnote).foregroundStyle(.secondary)
            Picker("Niveau", selection: $level) {
                ForEach(0..<defi.levels.count, id: \.self) { i in
                    Text(store.unlocked(defi.id, i) ? defi.levelLabel(i) : "\(levelNames[i]) 🔒")
                        .tag(i)
                }
            }
            .onChange(of: level) { _, new in
                if !store.unlocked(defi.id, new) { level = store.highestUnlocked(defi) }
            }

            Section(defi.ladder != nil ? "Paliers de" : "\(defi.rounds(level)) tour\(defi.rounds(level) > 1 ? "s" : "") de") {
                ForEach(defi.items, id: \.self) { it in
                    HStack {
                        Text(it.name)
                        Spacer()
                        if let l = defi.ladder {
                            Text(l.indices.map { "\(defi.qty(it, level: level, round: $0))" }.joined(separator: "-")).font(.footnote).bold()
                        } else {
                            Text(it.unit.isEmpty ? "\(defi.qty(it, level: level, round: 0))" : "\(defi.qty(it, level: level, round: 0)) \(it.unit)").bold()
                        }
                    }
                }
                if defi.rest > 0 {
                    Text("Repos \(defi.rest / 60) min entre les tours").font(.footnote).foregroundStyle(.secondary)
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
    @State private var restUntil: Date?

    private let accent = Color(red: 0.96, green: 0.49, blue: 0.54)
    private var rounds: Int { defi.rounds(level) }
    private var isRunning: Bool { startDate != nil && !finished }

    private func elapsed(at now: Date) -> Double {
        accumulated + (startDate.map { now.timeIntervalSince($0) } ?? 0)
    }

    private func restLeft(at now: Date) -> Double {
        guard let r = restUntil else { return 0 }
        return max(0, r.timeIntervalSince(now))
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
            let rest = restLeft(at: ctx.date)
            let k = min(splits.count, rounds - 1)
            VStack(spacing: 2) {
                HStack {
                    Text(defi.ladder != nil ? "Palier \(k + 1)/\(rounds)" : "Tour \(k + 1)/\(rounds)")
                        .font(.headline)
                        .foregroundStyle(accent)
                    Spacer()
                    Label("\(Int(workout.heartRate))", systemImage: "heart.fill")
                        .font(.footnote).foregroundStyle(.red)
                }
                Text(clock(t, tenths: true))
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .minimumScaleFactor(0.6)
                if rest > 0 {
                    Text("Repos \(clock(rest))").font(.footnote.bold()).foregroundStyle(.cyan)
                } else {
                    Text(defi.items.map { defi.line($0, level: level, round: k) }.joined(separator: " · "))
                        .font(.footnote)
                        .lineLimit(3)
                        .minimumScaleFactor(0.6)
                    ghostText.font(.caption2)
                }
                Button {
                    lap(at: t)
                } label: {
                    Text(rest > 0 ? "Repos…" : (splits.count + 1 >= rounds ? "🏁 Terminé" : "✓ Tour"))
                        .font(.title3.bold())
                        .frame(maxWidth: .infinity)
                }
                .tint(accent)
                .disabled(startDate == nil || rest > 0)
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
            Text("Premier passage").foregroundStyle(.secondary)
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
                    HStack { Text(defi.ladder != nil ? "Palier \(i + 1)" : "Tour \(i + 1)"); Spacer(); Text(clock(s - prev)) }
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
        guard isRunning, restLeft(at: Date()) == 0 else { return }
        splits.append(t)
        if splits.count >= rounds {
            finish(at: t)
            return
        }
        WKInterfaceDevice.current().play(.click)
        if defi.rest > 0 {
            let end = Date().addingTimeInterval(Double(defi.rest))
            restUntil = end
            Task {
                try? await Task.sleep(nanoseconds: UInt64(defi.rest) * 1_000_000_000)
                if restUntil == end {
                    restUntil = nil
                    WKInterfaceDevice.current().play(.start)
                }
            }
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
        restUntil = nil
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
