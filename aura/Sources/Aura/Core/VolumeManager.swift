import Foundation
import AppKit

struct VolumeInfo: Identifiable, Hashable {
    let url: URL
    let name: String
    let format: String
    let total: Int64
    let free: Int64
    let isRemovable: Bool
    let isEjectable: Bool
    let isInternal: Bool
    let isReadOnly: Bool
    let isNetwork: Bool
    var id: String { url.path }
    var used: Int64 { max(0, total - free) }
    var usedRatio: Double { total > 0 ? Double(used) / Double(total) : 0 }
    var icon: NSImage { NSWorkspace.shared.icon(forFile: url.path) }
    /// FAT / exFAT / NTFS : formats où macOS crée des fichiers « ._ ».
    var isForeignFormat: Bool {
        let f = format.lowercased()
        return f.contains("fat") || f.contains("ms-dos") || f.contains("ntfs")
    }
    var kindLabel: String {
        if isNetwork { return "Réseau" }
        if isRemovable || isEjectable { return isInternal ? "Carte mémoire" : "Support externe" }
        return "Disque interne"
    }
    var symbol: String {
        if isNetwork { return "network" }
        if isRemovable && isInternal { return "sdcard.fill" }
        if isEjectable || isRemovable { return "externaldrive.fill" }
        return "internaldrive.fill"
    }
}

/// Fichier parasite trouvé sur un support (créé par macOS, Windows ou Office).
struct JunkFile: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    let kind: JunkKind
    var selected = true
}

enum JunkKind: String, CaseIterable, Identifiable {
    case dsStore = "Fichiers .DS_Store (Finder)"
    case appleDouble = "Fichiers « ._ » (métadonnées Mac)"
    case trash = "Corbeille du support"
    case spotlight = "Index Spotlight"
    case fsevents = "Journal d'événements macOS"
    case temporary = "Éléments temporaires"
    case windows = "Fichiers Windows (Thumbs.db, desktop.ini)"
    case officeLock = "Verrous Office (~$…)"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .dsStore: return "folder.badge.gearshape"
        case .appleDouble: return "doc.on.doc"
        case .trash: return "trash"
        case .spotlight: return "magnifyingglass"
        case .fsevents: return "list.bullet.rectangle"
        case .temporary: return "clock.arrow.circlepath"
        case .windows: return "pc"
        case .officeLock: return "lock.doc"
        }
    }
}

@MainActor
final class VolumeManager: ObservableObject {
    @Published var volumes: [VolumeInfo] = []
    @Published var junk: [String: [JunkFile]] = [:]      // par chemin de volume
    @Published var scanning: Set<String> = []
    @Published var message = ""
    @Published var lastMounted: VolumeInfo?

    private var observers: [NSObjectProtocol] = []

    var externalVolumes: [VolumeInfo] { volumes.filter { !$0.isInternal || $0.isRemovable || $0.isEjectable } }

    init() {
        refresh()
        let nc = NSWorkspace.shared.notificationCenter
        for name in [NSWorkspace.didMountNotification, NSWorkspace.didUnmountNotification, NSWorkspace.didRenameVolumeNotification] {
            observers.append(nc.addObserver(forName: name, object: nil, queue: .main) { [weak self] note in
                Task { @MainActor in
                    guard let self else { return }
                    let before = Set(self.volumes.map(\.id))
                    await self.refreshNow()
                    if name == NSWorkspace.didMountNotification,
                       let new = self.volumes.first(where: { !before.contains($0.id) && !$0.isInternal }) {
                        self.lastMounted = new
                        if UserDefaults.standard.bool(forKey: "aura.autoScanVolumes") {
                            await self.scanJunk(new)
                        }
                    }
                }
            })
        }
    }

    // MARK: Inventaire

    func refresh() {
        Task {
            let list = await Task.detached(priority: .userInitiated) { Self.readVolumes() }.value
            volumes = list
            let ids = Set(list.map(\.id))
            junk = junk.filter { ids.contains($0.key) }
        }
    }

    /// Variante qui attend la fin de la lecture (utilisée après branchement d'un support).
    func refreshNow() async {
        volumes = await Task.detached(priority: .userInitiated) { Self.readVolumes() }.value
    }

    nonisolated static func readVolumes() -> [VolumeInfo] {
        let keys: [URLResourceKey] = [.volumeNameKey, .volumeLocalizedFormatDescriptionKey,
                                      .volumeTotalCapacityKey, .volumeAvailableCapacityKey,
                                      .volumeIsRemovableKey, .volumeIsEjectableKey, .volumeIsInternalKey,
                                      .volumeIsReadOnlyKey, .volumeIsLocalKey, .volumeIsBrowsableKey]
        let urls = FS.fm.mountedVolumeURLs(includingResourceValuesForKeys: keys, options: [.skipHiddenVolumes]) ?? []
        return urls.compactMap { url -> VolumeInfo? in
            guard let v = try? url.resourceValues(forKeys: Set(keys)), v.volumeIsBrowsable != false else { return nil }
            // On masque les volumes système techniques (Preboot, VM, Update…)
            if url.path.hasPrefix("/System/Volumes") { return nil }
            return VolumeInfo(url: url,
                              name: v.volumeName ?? url.lastPathComponent,
                              format: v.volumeLocalizedFormatDescription ?? "—",
                              total: Int64(v.volumeTotalCapacity ?? 0),
                              free: Int64(v.volumeAvailableCapacity ?? 0),
                              isRemovable: v.volumeIsRemovable ?? false,
                              isEjectable: v.volumeIsEjectable ?? false,
                              isInternal: v.volumeIsInternal ?? true,
                              isReadOnly: v.volumeIsReadOnly ?? false,
                              isNetwork: !(v.volumeIsLocal ?? true))
        }
        .sorted { a, b in
            if a.isInternal != b.isInternal { return !a.isInternal }   // externes d'abord
            return a.name.localizedCaseInsensitiveCompare(b.name) == .orderedAscending
        }
    }

    // MARK: Fichiers parasites

    nonisolated static func classify(_ url: URL, isDir: Bool, depth: Int) -> JunkKind? {
        let n = url.lastPathComponent
        if depth == 1 && isDir {
            switch n {
            case ".Trashes": return .trash
            case ".Spotlight-V100": return .spotlight
            case ".fseventsd": return .fsevents
            case ".TemporaryItems", "$RECYCLE.BIN", "System Volume Information": return n == ".TemporaryItems" ? .temporary : .windows
            default: break
            }
        }
        if isDir { return nil }
        if n == ".DS_Store" { return .dsStore }
        if n.hasPrefix("._") { return .appleDouble }
        if n == "Thumbs.db" || n == "desktop.ini" || n == "ehthumbs.db" { return .windows }
        if n.hasPrefix("~$") { return .officeLock }
        return nil
    }

    func scanJunk(_ volume: VolumeInfo) async {
        scanning.insert(volume.id)
        let root = volume.url
        let found: [JunkFile] = await Task.detached(priority: .userInitiated) {
            var out: [JunkFile] = []
            let keys: [URLResourceKey] = [.isDirectoryKey, .isSymbolicLinkKey]
            guard let e = FS.fm.enumerator(at: root, includingPropertiesForKeys: keys, options: [],
                                           errorHandler: { _, _ in true }) else { return [] }
            for case let url as URL in e {
                let v = try? url.resourceValues(forKeys: Set(keys))
                if v?.isSymbolicLink == true { continue }
                let isDir = v?.isDirectory ?? false
                if let kind = Self.classify(url, isDir: isDir, depth: e.level) {
                    out.append(JunkFile(url: url, size: FS.size(of: url), kind: kind))
                    if isDir { e.skipDescendants() }
                } else if isDir, [".Spotlight-V100", ".fseventsd", ".DocumentRevisions-V100"].contains(url.lastPathComponent) {
                    e.skipDescendants()
                }
            }
            return out
        }.value
        junk[volume.id] = found
        scanning.remove(volume.id)
    }

    func junkSize(_ v: VolumeInfo, selectedOnly: Bool = false) -> Int64 {
        (junk[v.id] ?? []).filter { !selectedOnly || $0.selected }.reduce(Int64(0)) { $0 + $1.size }
    }

    func toggle(volume: VolumeInfo, kind: JunkKind) {
        guard var list = junk[volume.id] else { return }
        let newValue = !list.filter { $0.kind == kind }.allSatisfy(\.selected)
        for i in list.indices where list[i].kind == kind { list[i].selected = newValue }
        junk[volume.id] = list
    }

    /// Suppression définitive : sur un support externe, la Corbeille ne libère pas de place.
    func cleanJunk(_ volume: VolumeInfo) async {
        let targets = (junk[volume.id] ?? []).filter(\.selected)
        let (freed, failed): (Int64, Int) = await Task.detached {
            var freed: Int64 = 0, failed = 0
            for f in targets {
                if f.kind == .trash || f.kind == .spotlight || f.kind == .fsevents {
                    // On vide le contenu, on garde le dossier
                    for child in FS.children(f.url) {
                        let s = FS.size(of: child)
                        if (try? FS.fm.removeItem(at: child)) != nil { freed += s } else { failed += 1 }
                    }
                } else if (try? FS.fm.removeItem(at: f.url)) != nil {
                    freed += f.size
                } else { failed += 1 }
            }
            return (freed, failed)
        }.value
        junk[volume.id]?.removeAll(where: \.selected)
        message = "\(volume.name) : \(Fmt.bytes(freed)) libérés" + (failed > 0 ? " (\(failed) éléments protégés)" : "")
        refresh()
    }

    // MARK: Actions sur le support

    func eject(_ volume: VolumeInfo) {
        do {
            try NSWorkspace.shared.unmountAndEjectDevice(at: volume.url)
            message = "\(volume.name) éjecté, tu peux le débrancher."
        } catch {
            message = "Impossible d'éjecter \(volume.name) : un fichier est peut-être encore ouvert."
        }
        refresh()
    }

    /// Empêche Spotlight et le journal macOS d'écrire sur ce support (idéal clé USB autoradio / TV).
    func protect(_ volume: VolumeInfo) {
        let root = volume.url
        FS.fm.createFile(atPath: root.appendingPathComponent(".metadata_never_index").path, contents: Data())
        let fse = root.appendingPathComponent(".fseventsd")
        try? FS.fm.createDirectory(at: fse, withIntermediateDirectories: true)
        FS.fm.createFile(atPath: fse.appendingPathComponent("no_log").path, contents: Data())
        message = "\(volume.name) : Spotlight et le journal macOS désactivés sur ce support."
    }

    func isProtected(_ volume: VolumeInfo) -> Bool {
        FS.exists(volume.url.appendingPathComponent(".metadata_never_index"))
    }

    /// Réglage global macOS : ne plus créer de .DS_Store sur les supports USB et réseau.
    nonisolated static var dsStoreBlocked: Bool {
        let d = UserDefaults(suiteName: "com.apple.desktopservices")
        return d?.bool(forKey: "DSDontWriteUSBStores") == true
    }

    func setDSStoreBlocked(_ on: Bool) {
        for key in ["DSDontWriteUSBStores", "DSDontWriteNetworkStores"] {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/defaults")
            p.arguments = on ? ["write", "com.apple.desktopservices", key, "-bool", "true"]
                             : ["delete", "com.apple.desktopservices", key]
            try? p.run(); p.waitUntilExit()
        }
        message = on ? "Plus de .DS_Store sur les supports externes (effectif après redémarrage de session)."
                     : "Comportement par défaut de macOS rétabli."
        objectWillChange.send()
    }

    /// Supprime les « ._ » via l'outil Apple dot_clean (fusionne les métadonnées proprement).
    func dotClean(_ volume: VolumeInfo) async {
        let path = volume.url.path
        await Task.detached {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/sbin/dot_clean")
            p.arguments = ["-m", path]
            try? p.run(); p.waitUntilExit()
        }.value
        message = "\(volume.name) : métadonnées « ._ » nettoyées avec dot_clean."
        await scanJunk(volume)
    }
}
