import Foundation
import SwiftUI

struct CleanItem: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    var selected: Bool
    var name: String { url.lastPathComponent }
}

enum RemovalMode { case trash, permanent }

struct CleanCategory: Identifiable {
    let id: String
    let name: String
    let icon: String
    let detail: String
    let tint: Color
    let defaultSelected: Bool
    let mode: RemovalMode
    var items: [CleanItem] = []

    var totalSize: Int64 { items.reduce(0) { $0 + $1.size } }
    var selectedSize: Int64 { items.filter(\.selected).reduce(0) { $0 + $1.size } }
    var isSelected: Bool { !items.isEmpty && items.allSatisfy(\.selected) }
}

/// Définition d'une catégorie : comment trouver ses éléments.
struct CategorySpec: @unchecked Sendable {
    let id, name, icon, detail: String
    let tint: Color
    let defaultSelected: Bool
    var mode: RemovalMode = .trash
    /// Renvoie les éléments candidats (chaque élément = un fichier ou dossier supprimable).
    let collect: () -> [URL]
}

/// Catalogue des catégories (non isolé : exécuté en arrière-plan).
enum CleanCatalog {

    static func kids(_ paths: [String]) -> [URL] {
        paths.map(FS.url).filter(FS.exists).flatMap { FS.children($0) }
    }
    static func whole(_ paths: [String]) -> [URL] {
        paths.map(FS.url).filter(FS.exists)
    }

    static let specs: [CategorySpec] = [
        CategorySpec(id: "caches", name: "Caches utilisateur", icon: "archivebox.fill",
                     detail: "Fichiers temporaires que les apps recréent automatiquement.",
                     tint: .blue, defaultSelected: true, mode: .permanent) {
            kids(["~/Library/Caches"])
        },
        CategorySpec(id: "logs", name: "Journaux système et apps", icon: "doc.text.fill",
                     detail: "Fichiers .log, rapports de diagnostic et de plantage.",
                     tint: .teal, defaultSelected: true, mode: .permanent) {
            kids(["~/Library/Logs", "~/Library/Logs/DiagnosticReports",
                  "~/Library/Application Support/CrashReporter"])
                .filter { $0.lastPathComponent != "DiagnosticReports" }
        },
        CategorySpec(id: "browsers", name: "Données des navigateurs", icon: "globe",
                     detail: "Caches Chrome, Edge, Brave, Firefox, Safari (pas les mots de passe ni l'historique).",
                     tint: .orange, defaultSelected: true, mode: .permanent) {
            var r: [URL] = []
            for base in ["~/Library/Application Support/Google/Chrome",
                         "~/Library/Application Support/Microsoft Edge",
                         "~/Library/Application Support/BraveSoftware/Brave-Browser"] {
                for profile in FS.children(FS.url(base)) where profile.lastPathComponent == "Default" || profile.lastPathComponent.hasPrefix("Profile") {
                    r += whole(["Cache", "Code Cache", "GPUCache", "Service Worker/CacheStorage"]
                        .map { profile.appendingPathComponent($0).path })
                }
            }
            r += whole(["~/Library/Containers/com.apple.Safari/Data/Library/Caches"])
            for p in FS.children(FS.url("~/Library/Application Support/Firefox/Profiles")) {
                r += whole([p.appendingPathComponent("cache2").path, p.appendingPathComponent("startupCache").path])
            }
            return r
        },
        CategorySpec(id: "xcode", name: "Déchets Xcode", icon: "hammer.fill",
                     detail: "DerivedData, caches de simulateurs, symboles d'appareils anciens.",
                     tint: .indigo, defaultSelected: true, mode: .permanent) {
            kids(["~/Library/Developer/Xcode/DerivedData",
                  "~/Library/Developer/Xcode/iOS DeviceSupport",
                  "~/Library/Developer/Xcode/watchOS DeviceSupport",
                  "~/Library/Developer/CoreSimulator/Caches"])
        },
        CategorySpec(id: "dev", name: "Caches développeur", icon: "terminal.fill",
                     detail: "npm, Yarn, pip, Gradle, CocoaPods, Homebrew.",
                     tint: .purple, defaultSelected: true, mode: .permanent) {
            whole(["~/.npm/_cacache", "~/.gradle/caches", "~/.cache/pip",
                   "~/Library/Caches/CocoaPods", "~/.cocoapods/repos/trunk"])
        },
        CategorySpec(id: "ai", name: "Déchets IA", icon: "brain.head.profile",
                     detail: "Caches et modèles locaux d'outils IA (Ollama, LM Studio, Hugging Face, Whisper…). Les modèles se retéléchargent.",
                     tint: .purple, defaultSelected: false) {
            whole(["~/.cache/huggingface", "~/.cache/whisper", "~/.cache/torch", "~/.cache/lm-studio",
                   "~/Library/Application Support/Cursor/Cache", "~/Library/Application Support/Cursor/CachedData",
                   "~/Library/Application Support/Code/CachedData", "~/Library/Application Support/Code/Cache"])
            + kids(["~/.ollama/models/blobs", "~/.lmstudio/models", "~/Library/Application Support/DiffusionBee/downloads"])
        },
        CategorySpec(id: "photos", name: "Déchets Photos et médias", icon: "photo.on.rectangle.angled",
                     detail: "Caches d'analyse Photos, vignettes, rendus de Final Cut et iMovie.",
                     tint: .pink, defaultSelected: true, mode: .permanent) {
            whole(["~/Library/Containers/com.apple.photoanalysisd/Data/Library/Caches",
                   "~/Library/Containers/com.apple.mediaanalysisd/Data/Library/Caches",
                   "~/Movies/iMovie Library.imovielibrary/Render Files",
                   "~/Movies/iMovie Theater.theater/Render Files"])
            + FS.children(FS.url("~/Movies")).filter { $0.pathExtension == "fcpbundle" }
                .flatMap { lib in FS.children(lib).map { $0.appendingPathComponent("Render Files") } }
                .filter(FS.exists)
        },
        CategorySpec(id: "music", name: "Déchets Musique et iOS", icon: "music.note",
                     detail: "Mises à jour logicielles iPhone/iPad téléchargées par le Mac.",
                     tint: .red, defaultSelected: true, mode: .permanent) {
            whole(["~/Library/iTunes/iPhone Software Updates", "~/Library/iTunes/iPad Software Updates"])
        },
        CategorySpec(id: "mail", name: "Pièces jointes Mail", icon: "paperclip",
                     detail: "Copies locales des pièces jointes déjà ouvertes (restent sur le serveur).",
                     tint: .cyan, defaultSelected: false) {
            kids(["~/Library/Containers/com.apple.mail/Data/Library/Mail Downloads"])
        },
        CategorySpec(id: "ios", name: "Sauvegardes iPhone / iPad", icon: "iphone",
                     detail: "Anciennes sauvegardes locales d'appareils iOS. Vérifie avant de supprimer.",
                     tint: .pink, defaultSelected: false) {
            kids(["~/Library/Application Support/MobileSync/Backup"])
        },
        CategorySpec(id: "updates", name: "Mises à jour et installeurs", icon: "shippingbox.fill",
                     detail: "Fichiers .dmg, .pkg et .zip d'installation qui traînent dans Téléchargements.",
                     tint: .mint, defaultSelected: false) {
            FS.children(FS.url("~/Downloads"))
                .filter { ["dmg", "pkg", "mpkg", "xip"].contains($0.pathExtension.lowercased()) }
        },
        CategorySpec(id: "downloads", name: "Vieux téléchargements", icon: "arrow.down.circle.fill",
                     detail: "Éléments de Téléchargements non ouverts depuis plus de 90 jours.",
                     tint: .yellow, defaultSelected: false) {
            let limit = Date().addingTimeInterval(-90 * 86400)
            return FS.children(FS.url("~/Downloads"), hidden: false).filter {
                let v = try? $0.resourceValues(forKeys: [.contentAccessDateKey, .contentModificationDateKey])
                let d = v?.contentAccessDate ?? v?.contentModificationDate ?? Date()
                return d < limit
            }
        },
        CategorySpec(id: "trash", name: "Corbeilles", icon: "trash.fill",
                     detail: "Corbeille du Mac et des supports externes. Suppression définitive.",
                     tint: .red, defaultSelected: true, mode: .permanent) {
            FS.children(FS.url("~/.Trash"))
            + FS.children(URL(fileURLWithPath: "/Volumes"))
                .flatMap { FS.children($0.appendingPathComponent(".Trashes/\(getuid())")) }
        }
    ]

}

@MainActor
final class CleanupEngine: ObservableObject {
    @Published var categories: [CleanCategory] = []
    @Published var isScanning = false
    @Published var isCleaning = false
    @Published var progressLabel = ""
    @Published var progress: Double = 0
    @Published var lastFreed: Int64 = 0
    @Published var lastFailed = 0
    @Published var lastScanDate: Date?

    @Pref("aura.exclusions") private var exclusionsRaw = ""
    @Pref("aura.totalFreed") var totalFreed: Double = 0

    var exclusions: [String] {
        get { exclusionsRaw.split(separator: "\n").map(String.init).filter { !$0.isEmpty } }
        set { exclusionsRaw = newValue.joined(separator: "\n") }
    }

    var totalFound: Int64 { categories.reduce(0) { $0 + $1.totalSize } }
    var totalSelected: Int64 { categories.reduce(0) { $0 + $1.selectedSize } }

    // MARK: - Scan

    func scan() async {
        guard !isScanning else { return }
        isScanning = true
        progress = 0
        categories = []
        let excluded = exclusions
        let specs = CleanCatalog.specs

        for (i, spec) in specs.enumerated() {
            progressLabel = "Analyse : \(spec.name)…"
            let items: [CleanItem] = await Task.detached(priority: .userInitiated) {
                spec.collect()
                    .filter { url in !excluded.contains { url.path.hasPrefix(($0 as NSString).expandingTildeInPath) } }
                    .map { CleanItem(url: $0, size: FS.size(of: $0), selected: spec.defaultSelected) }
                    .filter { $0.size > 0 }
                    .sorted { $0.size > $1.size }
            }.value
            var cat = CleanCategory(id: spec.id, name: spec.name, icon: spec.icon, detail: spec.detail,
                                    tint: spec.tint, defaultSelected: spec.defaultSelected, mode: spec.mode)
            cat.items = items
            categories.append(cat)
            progress = Double(i + 1) / Double(specs.count)
        }
        progressLabel = "Analyse terminée"
        lastScanDate = Date()
        isScanning = false
    }

    /// Nettoyage silencieux planifié : uniquement ce qui se recrée tout seul (caches, journaux, Xcode…).
    func autoClean() async -> Int64 {
        await scan()
        let safe: Set<String> = ["caches", "logs", "browsers", "xcode", "dev", "photos"]
        for i in categories.indices {
            for j in categories[i].items.indices { categories[i].items[j].selected = safe.contains(categories[i].id) }
        }
        await clean()
        return lastFreed
    }

    // MARK: - Sélection

    func toggleCategory(_ id: String) {
        guard let i = categories.firstIndex(where: { $0.id == id }) else { return }
        let newValue = !categories[i].isSelected
        for j in categories[i].items.indices { categories[i].items[j].selected = newValue }
    }

    func toggleItem(category: String, item: UUID) {
        guard let i = categories.firstIndex(where: { $0.id == category }),
              let j = categories[i].items.firstIndex(where: { $0.id == item }) else { return }
        categories[i].items[j].selected.toggle()
    }

    // MARK: - Nettoyage

    func clean() async {
        guard !isCleaning else { return }
        isCleaning = true
        progress = 0
        let work = categories.flatMap { c in c.items.filter(\.selected).map { (c.mode, $0) } }
        var freed: Int64 = 0, failed = 0

        for (n, (mode, item)) in work.enumerated() {
            progressLabel = "Nettoyage : \(item.name)"
            let ok: Bool = await Task.detached(priority: .userInitiated) {
                switch mode {
                case .trash: return FS.trash(item.url)
                case .permanent: return (try? FS.fm.removeItem(at: item.url)) != nil
                }
            }.value
            if ok { freed += item.size } else { failed += 1 }
            progress = Double(n + 1) / Double(max(1, work.count))
        }

        for i in categories.indices { categories[i].items.removeAll(where: \.selected) }
        lastFreed = freed
        lastFailed = failed
        totalFreed += Double(freed)
        progressLabel = "Terminé"
        isCleaning = false
    }
}
