import Foundation

struct TidyMove: Identifiable, Codable, Hashable {
    var id: String { from }
    let from: String
    let to: String
    var fileName: String { (from as NSString).lastPathComponent }
    var destinationFolder: String { ((to as NSString).deletingLastPathComponent as NSString).lastPathComponent }
}

enum TidyMode: String, CaseIterable, Identifiable {
    case byType = "Par type (Images, Documents…)"
    case byMonth = "Par mois (2026-10…)"
    var id: String { rawValue }
}

/// Rangement automatique du Bureau et des Téléchargements.
/// Ne supprime jamais rien : déplace les fichiers dans des sous-dossiers, et peut tout annuler.
@MainActor
final class TidyManager: ObservableObject {
    @Published var plan: [TidyMove] = []
    @Published var isWorking = false
    @Published var message = ""
    @Published var lastBatch: [TidyMove] = []

    @Pref("aura.tidy.desktop") var desktop = true
    @Pref("aura.tidy.downloads") var downloads = true
    @Pref("aura.tidy.mode") var modeRaw = TidyMode.byType.rawValue
    @Pref("aura.tidy.archiveDays") var archiveDays = 30
    @Pref("aura.tidy.auto") var autoWeekly = false
    @Pref("aura.tidy.lastAuto") var lastAuto: Double = 0

    var mode: TidyMode {
        get { TidyMode(rawValue: modeRaw) ?? .byType }
        set { modeRaw = newValue.rawValue; objectWillChange.send() }
    }

    nonisolated static let categories: [(String, Set<String>)] = [
        ("Images", ["jpg", "jpeg", "png", "heic", "heif", "gif", "webp", "tif", "tiff", "bmp", "svg", "raw", "dng", "cr2", "nef", "arw", "psd"]),
        ("Vidéos", ["mov", "mp4", "m4v", "avi", "mkv", "webm"]),
        ("Audio", ["mp3", "m4a", "wav", "aiff", "aif", "flac", "aac", "ogg"]),
        ("Documents", ["pdf", "doc", "docx", "xls", "xlsx", "csv", "ppt", "pptx", "pages", "numbers", "key", "txt", "rtf", "md", "odt", "ods", "eml", "msg"]),
        ("Archives", ["zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz"]),
        ("Installeurs", ["dmg", "pkg", "mpkg", "xip", "iso"]),
        ("Code", ["html", "htm", "css", "js", "json", "py", "swift", "sh", "xml", "yml", "yaml", "sql", "gs"]),
        ("Impression 3D", ["stl", "3mf", "obj", "gcode", "step", "stp"])
    ]

    nonisolated static func category(for ext: String) -> String {
        let e = ext.lowercased()
        return categories.first { $0.1.contains(e) }?.0 ?? "Autres"
    }

    private var undoURL: URL {
        let dir = FS.url("~/Library/Application Support/Aura")
        try? FS.fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("rangement-annulation.json")
    }

    init() {
        if let d = try? Data(contentsOf: undoURL), let m = try? JSONDecoder().decode([TidyMove].self, from: d) {
            lastBatch = m
        }
    }

    var folders: [URL] {
        var f: [URL] = []
        if desktop { f.append(FS.url("~/Desktop")) }
        if downloads { f.append(FS.url("~/Downloads")) }
        return f
    }

    // MARK: Plan

    func preview() async {
        isWorking = true
        let folders = self.folders, mode = self.mode, days = archiveDays
        plan = await Task.detached { Self.makePlan(folders: folders, mode: mode, archiveDays: days) }.value
        message = plan.isEmpty ? "Rien à ranger : tout est déjà en ordre ✨" : "\(plan.count) fichier(s) à ranger"
        isWorking = false
    }

    nonisolated static func makePlan(folders: [URL], mode: TidyMode, archiveDays: Int) -> [TidyMove] {
        let keys: Set<URLResourceKey> = [.isDirectoryKey, .isPackageKey, .contentModificationDateKey, .addedToDirectoryDateKey]
        let recent = Date().addingTimeInterval(-10 * 60)         // on ne touche pas aux fichiers en cours d'utilisation
        let archiveLimit = Date().addingTimeInterval(-Double(archiveDays) * 86400)
        let monthFmt = DateFormatter()
        monthFmt.dateFormat = "yyyy-MM"
        var moves: [TidyMove] = []
        for folder in folders {
            for url in FS.children(folder, hidden: false) {
                guard let v = try? url.resourceValues(forKeys: keys) else { continue }
                // Les dossiers ne sont jamais déplacés, sauf les apps et paquets (qui sont des « fichiers »)
                if v.isDirectory == true && v.isPackage != true { continue }
                let ext = url.pathExtension.lowercased()
                if ["download", "crdownload", "part", "localized"].contains(ext) || url.lastPathComponent == ".DS_Store" { continue }
                let date = v.addedToDirectoryDate ?? v.contentModificationDate ?? Date()
                if date > recent { continue }

                let dest: URL
                if archiveDays > 0 && date < archiveLimit {
                    dest = folder.appendingPathComponent("Archives").appendingPathComponent(monthFmt.string(from: date))
                } else if mode == .byMonth {
                    dest = folder.appendingPathComponent(monthFmt.string(from: date))
                } else {
                    dest = folder.appendingPathComponent(category(for: ext))
                }
                moves.append(TidyMove(from: url.path, to: dest.appendingPathComponent(url.lastPathComponent).path))
            }
        }
        return moves.sorted { $0.to < $1.to }
    }

    func remove(_ m: TidyMove) { plan.removeAll { $0.id == m.id } }

    // MARK: Exécution

    func apply() async {
        guard !plan.isEmpty else { return }
        isWorking = true
        let moves = plan
        let done = await Task.detached { Self.perform(moves) }.value
        lastBatch = done
        if let d = try? JSONEncoder().encode(done) { try? d.write(to: undoURL) }
        plan = []
        message = "\(done.count) fichier(s) rangé(s). Tu peux annuler à tout moment."
        isWorking = false
    }

    /// Déplace en évitant d'écraser : « photo.jpg » devient « photo 2.jpg » si besoin.
    nonisolated static func perform(_ moves: [TidyMove]) -> [TidyMove] {
        var done: [TidyMove] = []
        for m in moves {
            let src = URL(fileURLWithPath: m.from)
            guard FS.exists(src) else { continue }
            var dst = URL(fileURLWithPath: m.to)
            try? FS.fm.createDirectory(at: dst.deletingLastPathComponent(), withIntermediateDirectories: true)
            var n = 2
            let stem = dst.deletingPathExtension().lastPathComponent, ext = dst.pathExtension
            while FS.exists(dst) {
                dst = dst.deletingLastPathComponent().appendingPathComponent(ext.isEmpty ? "\(stem) \(n)" : "\(stem) \(n).\(ext)")
                n += 1
            }
            if (try? FS.fm.moveItem(at: src, to: dst)) != nil { done.append(TidyMove(from: m.from, to: dst.path)) }
        }
        return done
    }

    func undo() async {
        guard !lastBatch.isEmpty else { return }
        isWorking = true
        let reverse = lastBatch.map { TidyMove(from: $0.to, to: $0.from) }
        let restored = await Task.detached { Self.perform(reverse) }.value
        // Supprime les sous-dossiers devenus vides
        let dirs = Set(lastBatch.map { URL(fileURLWithPath: $0.to).deletingLastPathComponent() })
        for d in dirs where FS.children(d).filter({ $0.lastPathComponent != ".DS_Store" }).isEmpty {
            try? FS.fm.removeItem(at: d)
        }
        message = "\(restored.count) fichier(s) remis à leur place."
        lastBatch = []
        try? FS.fm.removeItem(at: undoURL)
        isWorking = false
    }

    /// Rangement hebdomadaire automatique (appelé par le centre de santé).
    func autoRunIfDue(notify: (String, String) -> Void) async {
        guard autoWeekly, Date().timeIntervalSince1970 - lastAuto > 7 * 86400 else { return }
        lastAuto = Date().timeIntervalSince1970
        await preview()
        guard !plan.isEmpty else { return }
        let n = plan.count
        await apply()
        notify("Rangement automatique", "\(n) fichier(s) du Bureau et des Téléchargements rangés. Annulable dans Aura › Rangement.")
    }
}
