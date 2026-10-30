import Foundation
import AppKit

/// Outils bas niveau d'accès disque, partagés par tous les modules.
enum FS {
    static let fm = FileManager.default
    static let home = fm.homeDirectoryForCurrentUser

    static func url(_ path: String) -> URL {
        URL(fileURLWithPath: (path as NSString).expandingTildeInPath)
    }

    static func exists(_ url: URL) -> Bool { fm.fileExists(atPath: url.path) }

    private static let sizeKeys: Set<URLResourceKey> = [
        .isRegularFileKey, .totalFileAllocatedSizeKey, .fileAllocatedSizeKey, .isSymbolicLinkKey
    ]

    /// Taille réelle sur disque d'un fichier ou dossier (récursive).
    static func size(of url: URL, cancel: (() -> Bool)? = nil) -> Int64 {
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: url.path, isDirectory: &isDir) else { return 0 }
        if !isDir.boolValue { return fileSize(url) }
        guard let e = fm.enumerator(at: url, includingPropertiesForKeys: Array(sizeKeys),
                                    options: [], errorHandler: { _, _ in true }) else { return 0 }
        var total: Int64 = 0
        var n = 0
        for case let item as URL in e {
            n += 1
            if n % 2000 == 0, cancel?() == true { break }
            guard let v = try? item.resourceValues(forKeys: sizeKeys),
                  v.isRegularFile == true, v.isSymbolicLink != true else { continue }
            total += Int64(v.totalFileAllocatedSize ?? v.fileAllocatedSize ?? 0)
        }
        return total
    }

    static func fileSize(_ url: URL) -> Int64 {
        let v = try? url.resourceValues(forKeys: sizeKeys)
        return Int64(v?.totalFileAllocatedSize ?? v?.fileAllocatedSize ?? 0)
    }

    /// Enfants directs d'un dossier (sans erreur si inaccessible).
    static func children(_ url: URL, hidden: Bool = true) -> [URL] {
        let opts: FileManager.DirectoryEnumerationOptions = hidden ? [] : [.skipsHiddenFiles]
        return (try? fm.contentsOfDirectory(at: url, includingPropertiesForKeys: nil, options: opts)) ?? []
    }

    /// Envoie à la Corbeille (récupérable) — jamais de suppression définitive.
    @discardableResult
    static func trash(_ url: URL) -> Bool {
        do {
            try fm.trashItem(at: url, resultingItemURL: nil)
            return true
        } catch {
            return false
        }
    }

    /// Vide le contenu d'un dossier de cache en envoyant chaque élément à la Corbeille.
    static func trashContents(of url: URL) -> (freed: Int64, failed: Int) {
        var freed: Int64 = 0, failed = 0
        for child in children(url) {
            let s = size(of: child)
            if trash(child) { freed += s } else { failed += 1 }
        }
        return (freed, failed)
    }

    static func reveal(_ url: URL) {
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    /// Vérifie l'Accès complet au disque en testant un dossier protégé.
    static var hasFullDiskAccess: Bool {
        let probe = home.appendingPathComponent("Library/Safari")
        let tcc = home.appendingPathComponent("Library/Application Support/com.apple.TCC")
        return (try? fm.contentsOfDirectory(atPath: probe.path)) != nil
            || (try? fm.contentsOfDirectory(atPath: tcc.path)) != nil
    }

    static func openFullDiskAccessSettings() {
        if let u = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles") {
            NSWorkspace.shared.open(u)
        }
    }

    static func volumeInfo(_ url: URL = URL(fileURLWithPath: "/"), includePurgeable: Bool = false) -> (total: Int64, free: Int64, purgeable: Int64) {
        var keys: Set<URLResourceKey> = [.volumeTotalCapacityKey, .volumeAvailableCapacityKey]
        if includePurgeable { keys.insert(.volumeAvailableCapacityForImportantUsageKey) }
        let v = try? url.resourceValues(forKeys: keys)
        let total = Int64(v?.volumeTotalCapacity ?? 0)
        let free = Int64(v?.volumeAvailableCapacity ?? 0)
        let important = v?.volumeAvailableCapacityForImportantUsage ?? free
        return (total, free, max(0, important - free))
    }
}
