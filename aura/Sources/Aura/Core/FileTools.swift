import Foundation
import CryptoKit

struct FileEntry: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    let modified: Date?
    var selected = false
    var name: String { url.lastPathComponent }
    var kind: String {
        switch url.pathExtension.lowercased() {
        case "mov", "mp4", "m4v", "avi", "mkv": return "Vidéo"
        case "jpg", "jpeg", "png", "heic", "raw", "cr2", "nef", "arw", "dng", "tiff": return "Image"
        case "zip", "rar", "7z", "tar", "gz", "dmg", "pkg", "iso": return "Archive"
        case "mp3", "wav", "aiff", "flac", "m4a": return "Audio"
        case "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "pages", "numbers", "key": return "Document"
        default: return "Autre"
        }
    }
}

struct DuplicateGroup: Identifiable {
    let id = UUID()
    var files: [FileEntry]
    var size: Int64 { files.first?.size ?? 0 }
    var wasted: Int64 { size * Int64(max(0, files.count - 1)) }
}

struct SpaceNode: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    let isDirectory: Bool
    var name: String { url.lastPathComponent }
}

/// Moteur de recherche de fichiers (gros fichiers, doublons, carte de l'espace).
@MainActor
final class FileTools: ObservableObject {
    @Published var largeFiles: [FileEntry] = []
    @Published var duplicates: [DuplicateGroup] = []
    @Published var spaceNodes: [SpaceNode] = []
    @Published var spaceRoot: URL = FS.home
    @Published var isBusy = false
    @Published var status = ""
    @Published var scannedCount = 0

    private var cancelFlag = false
    func cancel() { cancelFlag = true }

    private nonisolated static let skipDirs: Set<String> = [
        "Library", ".Trash", "node_modules", ".git", "DerivedData", ".npm", ".cache"
    ]

    /// Parcourt tous les fichiers réguliers sous `root`, en ignorant les dossiers techniques.
    private nonisolated static func walk(_ root: URL, minSize: Int64, isCancelled: @escaping () -> Bool,
                                         onCount: @escaping (Int) -> Void) -> [FileEntry] {
        let keys: [URLResourceKey] = [.isRegularFileKey, .isDirectoryKey, .isPackageKey,
                                      .totalFileAllocatedSizeKey, .fileSizeKey, .contentModificationDateKey,
                                      .isSymbolicLinkKey]
        guard let e = FS.fm.enumerator(at: root, includingPropertiesForKeys: keys,
                                       options: [.skipsHiddenFiles], errorHandler: { _, _ in true }) else { return [] }
        var out: [FileEntry] = []
        var n = 0
        for case let url as URL in e {
            n += 1
            if n % 500 == 0 { onCount(n); if isCancelled() { break } }
            guard let v = try? url.resourceValues(forKeys: Set(keys)) else { continue }
            if v.isDirectory == true {
                if skipDirs.contains(url.lastPathComponent) || v.isPackage == true { e.skipDescendants() }
                continue
            }
            guard v.isRegularFile == true, v.isSymbolicLink != true else { continue }
            let size = Int64(v.fileSize ?? v.totalFileAllocatedSize ?? 0)
            if size >= minSize {
                out.append(FileEntry(url: url, size: size, modified: v.contentModificationDate))
            }
        }
        onCount(n)
        return out
    }

    // MARK: Gros et vieux fichiers

    func findLargeFiles(in root: URL, minSize: Int64) async {
        isBusy = true; cancelFlag = false; status = "Recherche des gros fichiers…"
        let result = await Task.detached(priority: .userInitiated) { [weak self] in
            Self.walk(root, minSize: minSize,
                      isCancelled: { false },
                      onCount: { c in Task { @MainActor in self?.scannedCount = c } })
        }.value
        largeFiles = result.sorted { $0.size > $1.size }
        status = "\(largeFiles.count) fichiers trouvés"
        isBusy = false
    }

    // MARK: Doublons

    private nonisolated static func hash(_ url: URL, limit: Int? = nil) -> String? {
        guard let h = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? h.close() }
        var hasher = SHA256()
        var read = 0
        while true {
            let chunk = h.readData(ofLength: 1 << 20)
            if chunk.isEmpty { break }
            hasher.update(data: chunk)
            read += chunk.count
            if let limit, read >= limit { break }
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    /// Analyse un ou plusieurs dossiers / disques (ex. le Mac + une clé USB) en une passe.
    func findDuplicates(in roots: [URL], minSize: Int64 = 100_000) async {
        isBusy = true; cancelFlag = false; status = "Inventaire des fichiers…"
        let groups: [DuplicateGroup] = await Task.detached(priority: .userInitiated) { [weak self] in
            var seen = Set<String>()
            var files: [FileEntry] = []
            for root in roots {
                for f in Self.walk(root, minSize: minSize, isCancelled: { false },
                                   onCount: { c in Task { @MainActor in self?.scannedCount = c } })
                where seen.insert(f.url.standardizedFileURL.path).inserted {
                    files.append(f)
                }
            }
            // 1) même taille
            let bySize = Dictionary(grouping: files, by: \.size).values.filter { $0.count > 1 }
            Task { @MainActor in self?.status = "Comparaison du contenu…" }
            var result: [DuplicateGroup] = []
            for sameSize in bySize {
                // 2) même début (1 Mo), 3) même empreinte complète
                let byPartial = Dictionary(grouping: sameSize) { Self.hash($0.url, limit: 1 << 20) ?? UUID().uuidString }
                for candidates in byPartial.values where candidates.count > 1 {
                    let byFull = Dictionary(grouping: candidates) { Self.hash($0.url) ?? UUID().uuidString }
                    for same in byFull.values where same.count > 1 {
                        result.append(DuplicateGroup(files: same))
                    }
                }
            }
            return result.sorted { $0.wasted > $1.wasted }
        }.value
        duplicates = groups
        applyKeepRule()
        let wasted = groups.reduce(Int64(0)) { $0 + $1.wasted }
        status = "\(groups.count) groupes de doublons — \(Fmt.bytes(wasted)) récupérables"
        isBusy = false
    }

    // MARK: Règles de sélection automatique

    enum KeepRule: String, CaseIterable, Identifiable {
        case oldest = "Garder le plus ancien"
        case newest = "Garder le plus récent"
        case shortestPath = "Garder le chemin le plus court"
        case onMac = "Garder la copie sur le Mac"
        case inFolder = "Garder celle du dossier préféré"
        var id: String { rawValue }
    }

    @Published var keepRule: KeepRule = .oldest
    @Published var preferredFolder: URL?

    /// Choisit la copie à conserver dans chaque groupe et coche toutes les autres.
    func applyKeepRule() {
        let rootVolume = (try? URL(fileURLWithPath: "/").resourceValues(forKeys: [.volumeIdentifierKey]))?.volumeIdentifier as? NSObject
        for g in duplicates.indices {
            let files = duplicates[g].files
            let keeper: FileEntry?
            switch keepRule {
            case .oldest:
                keeper = files.min { ($0.modified ?? .distantFuture) < ($1.modified ?? .distantFuture) }
            case .newest:
                keeper = files.max { ($0.modified ?? .distantPast) < ($1.modified ?? .distantPast) }
            case .shortestPath:
                keeper = files.min { $0.url.pathComponents.count < $1.url.pathComponents.count }
            case .onMac:
                keeper = files.first {
                    let v = (try? $0.url.resourceValues(forKeys: [.volumeIdentifierKey]))?.volumeIdentifier as? NSObject
                    return v != nil && v == rootVolume
                } ?? files.first
            case .inFolder:
                let base = preferredFolder?.standardizedFileURL.path ?? ""
                keeper = files.first { !base.isEmpty && $0.url.standardizedFileURL.path.hasPrefix(base + "/") } ?? files.first
            }
            for f in duplicates[g].files.indices {
                duplicates[g].files[f].selected = duplicates[g].files[f].id != keeper?.id
            }
        }
    }

    func selectAllDuplicates(_ on: Bool) {
        if on { applyKeepRule(); return }
        for g in duplicates.indices { for f in duplicates[g].files.indices { duplicates[g].files[f].selected = false } }
    }

    func toggleDuplicate(group: UUID, file: UUID) {
        guard let g = duplicates.firstIndex(where: { $0.id == group }),
              let f = duplicates[g].files.firstIndex(where: { $0.id == file }) else { return }
        duplicates[g].files[f].selected.toggle()
    }

    /// `permanent` : utile sur un support externe, où la Corbeille ne libère pas d'espace.
    func removeSelectedDuplicates(permanent: Bool = false) async -> Int64 {
        // Sécurité : on ne supprime jamais toutes les copies d'un groupe
        var targets: [FileEntry] = []
        for g in duplicates {
            let sel = g.files.filter(\.selected)
            if sel.count < g.files.count { targets += sel }
        }
        let freed = await Task.detached {
            targets.reduce(Int64(0)) { acc, f in
                let ok = permanent ? (try? FS.fm.removeItem(at: f.url)) != nil : FS.trash(f.url)
                return ok ? acc + f.size : acc
            }
        }.value
        let removed = Set(targets.map(\.id))
        duplicates = duplicates.compactMap { g in
            var g = g; g.files.removeAll { removed.contains($0.id) }
            return g.files.count > 1 ? g : nil
        }
        return freed
    }

    func removeLargeFiles() async -> Int64 {
        let targets = largeFiles.filter(\.selected)
        let freed = await Task.detached { targets.reduce(Int64(0)) { FS.trash($1.url) ? $0 + $1.size : $0 } }.value
        largeFiles.removeAll(where: \.selected)
        return freed
    }

    // MARK: Carte de l'espace

    func mapSpace(_ root: URL) async {
        isBusy = true
        spaceRoot = root
        status = "Calcul de l'occupation de \(root.lastPathComponent)…"
        spaceNodes = []
        let children = FS.children(root)
        // Calcul en parallèle des tailles des sous-dossiers
        let nodes: [SpaceNode] = await withTaskGroup(of: SpaceNode?.self) { group in
            for child in children {
                group.addTask(priority: .userInitiated) {
                    var isDir: ObjCBool = false
                    FS.fm.fileExists(atPath: child.path, isDirectory: &isDir)
                    let s = FS.size(of: child)
                    return s > 0 ? SpaceNode(url: child, size: s, isDirectory: isDir.boolValue) : nil
                }
            }
            var out: [SpaceNode] = []
            for await n in group { if let n { out.append(n) } }
            return out
        }
        spaceNodes = nodes.sorted { $0.size > $1.size }
        status = Fmt.bytes(spaceNodes.reduce(0) { $0 + $1.size })
        isBusy = false
    }
}
