import Foundation
import AVFoundation

/// Catégories de fichiers inutiles laissés par les caméras (Insta360 X/Ace Pro, GoPro, DJI).
enum CamCategory: String, CaseIterable, Identifiable {
    case proxies, technical, empty, duplicates, orphanProxies, shortClips, incomplete

    var id: String { rawValue }

    var title: String {
        switch self {
        case .proxies: return "Aperçus basse définition (LRV)"
        case .technical: return "Vignettes et fichiers techniques"
        case .empty: return "Fichiers vides ou interrompus"
        case .duplicates: return "Copies identiques"
        case .orphanProxies: return "Aperçus sans original"
        case .shortClips: return "Clips très courts (déclenchements involontaires ?)"
        case .incomplete: return "Vidéos 360 incomplètes"
        }
    }

    var detail: String {
        switch self {
        case .proxies:
            return "Copies légères créées par la caméra pour l'aperçu dans l'appli du téléphone. La vidéo originale pleine définition est bien présente : elles ne servent plus une fois les vidéos sur le Mac."
        case .technical:
            return "Vignettes (.THM), index et journaux de la caméra. Recréés si besoin, inutiles pour tes vidéos."
        case .empty:
            return "Fichiers de quelques octets, souvent laissés par une batterie vide ou une carte retirée pendant l'enregistrement."
        case .duplicates:
            return "Même contenu au bit près, par exemple une carte importée deux fois. L'exemplaire au nom d'origine est conservé."
        case .orphanProxies:
            return "L'original pleine définition n'est plus dans les dossiers analysés. Si tu l'as supprimé exprès, cet aperçu est la seule trace du clip : à vérifier avant de cocher."
        case .shortClips:
            return "Vidéos de moins de 3 secondes. Vérifie-les avant de cocher : un court clip peut être voulu."
        case .incomplete:
            return "Sur les X3, X2 et ONE X, une vidéo 360 tient en deux fichiers (un par objectif). Il manque ici le fichier « _00_ » : sans lui, la vidéo ne peut pas être assemblée."
        }
    }

    var icon: String {
        switch self {
        case .proxies: return "film.stack"
        case .technical: return "doc.badge.gearshape"
        case .empty: return "exclamationmark.triangle"
        case .duplicates: return "square.on.square"
        case .orphanProxies: return "questionmark.folder"
        case .shortClips: return "timer"
        case .incomplete: return "circle.lefthalf.filled"
        }
    }

    /// Coché d'office uniquement quand c'est sans risque.
    var defaultSelected: Bool {
        switch self {
        case .proxies, .technical, .empty, .duplicates: return true
        case .orphanProxies, .shortClips, .incomplete: return false
        }
    }
}

struct CamItem: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    let category: CamCategory
    let note: String
    var selected: Bool
}

/// Identifiant Insta360 / Ace Pro : VID_20240416_213000_00_001 → (type, clé "20240416_213000_001", objectif, aperçu ?)
struct InstaName {
    let type: String        // VID, PRO_VID, LRV, PRO_LRV, IMG
    let key: String
    let lens: Character
    let isProxy: Bool

    init?(_ stem: String) {
        var parts = stem.split(separator: "_").map(String.init)
        var prefix = ""
        if parts.first == "PRO" { prefix = "PRO_"; parts.removeFirst() }
        guard parts.count >= 5, ["VID", "LRV", "IMG"].contains(parts[0]),
              parts[1].count == 8, parts[2].count == 6, parts[3].count == 2,
              parts[1].allSatisfy(\.isNumber), parts[2].allSatisfy(\.isNumber) else { return nil }
        type = prefix + parts[0]
        key = "\(parts[1])_\(parts[2])_\(parts[4])"
        lens = parts[3].first ?? "0"
        isProxy = parts[0] == "LRV" || parts[3].last == "1"
    }
}

@MainActor
final class CameraCleaner: ObservableObject {
    @Published var sources: [URL] = []
    @Published var items: [CamItem] = []
    @Published var isScanning = false
    @Published var isDeleting = false
    @Published var progress: Double = 0
    @Published var status = ""
    @Published var scannedVideos = 0
    @Published var scannedBytes: Int64 = 0

    nonisolated static let mediaExts: Set<String> = ["mp4", "mov", "insv", "insp", "jpg", "jpeg", "dng", "heic", "360"]
    nonisolated static let proxyExts: Set<String> = ["lrv", "lrf"]
    nonisolated static let techExts: Set<String> = ["thm", "idx", "list", "log", "glv", "srt"]
    nonisolated static let videoExts: Set<String> = ["mp4", "mov", "insv", "360"]

    var selectedSize: Int64 { items.filter(\.selected).reduce(0) { $0 + $1.size } }
    var totalSize: Int64 { items.reduce(0) { $0 + $1.size } }
    func entries(in c: CamCategory) -> [CamItem] { items.filter { $0.category == c } }

    // MARK: Analyse

    func analyze() async {
        guard !isScanning, !sources.isEmpty else { return }
        isScanning = true
        items = []
        progress = 0
        status = "Inventaire des fichiers…"
        let roots = sources

        let found = await Task.detached(priority: .userInitiated) { Self.classify(roots: roots) }.value
        scannedVideos = found.videoCount
        scannedBytes = found.totalBytes
        var result = found.items
        progress = 0.4

        // Doublons (hors aperçus déjà repérés)
        status = "Recherche des copies identiques…"
        let flagged = Set(result.map(\.url))
        let media = found.media.filter { !flagged.contains($0.url) }
        let dupes = await Task.detached(priority: .userInitiated) { PhotoOrganizer.findDuplicates(media) }.value
        let sizes = Dictionary(found.media.map { ($0.url, $0.size) }, uniquingKeysWith: { a, _ in a })
        for d in dupes {
            result.append(CamItem(url: d.copy, size: sizes[d.copy] ?? 0, category: .duplicates,
                                  note: "identique à \(d.original.lastPathComponent)", selected: true))
        }
        progress = 0.6

        // Clips très courts (lecture de la durée des vidéos de taille modeste)
        status = "Mesure de la durée des clips…"
        let dupSet = Set(dupes.map(\.copy))
        let candidates = found.media.filter {
            $0.isVideo && $0.size < 400_000_000 && !flagged.contains($0.url) && !dupSet.contains($0.url)
        }
        for (i, m) in candidates.enumerated() {
            if let d = await Self.duration(m.url), d < 3 {
                result.append(CamItem(url: m.url, size: m.size, category: .shortClips,
                                      note: d.formatted(.number.precision(.fractionLength(1))) + " s", selected: false))
            }
            if i % 5 == 0 { progress = 0.6 + 0.4 * Double(i) / Double(max(1, candidates.count)) }
        }

        items = result.sorted { $0.size > $1.size }
        progress = 1
        status = items.isEmpty
            ? "Aucun fichier inutile trouvé dans \(found.videoCount) vidéo(s) analysée(s)."
            : "\(items.count) fichier(s) inutile(s) repéré(s) · \(Fmt.bytes(totalSize))"
        isScanning = false
    }

    struct ScanResult {
        var items: [CamItem] = []
        var media: [MediaItem] = []
        var videoCount = 0
        var totalBytes: Int64 = 0
    }

    nonisolated static func classify(roots: [URL]) -> ScanResult {
        var r = ScanResult()
        var files: [(url: URL, size: Int64, ext: String, stem: String, dirName: String)] = []
        var seen = Set<String>()
        for root in roots {
            guard let e = FS.fm.enumerator(at: root, includingPropertiesForKeys: [.fileSizeKey, .isDirectoryKey, .isPackageKey],
                                           options: [.skipsHiddenFiles], errorHandler: { _, _ in true }) else { continue }
            for case let u as URL in e {
                let v = try? u.resourceValues(forKeys: [.fileSizeKey, .isDirectoryKey, .isPackageKey])
                if v?.isDirectory == true {
                    if v?.isPackage == true { e.skipDescendants() }
                    continue
                }
                let ext = u.pathExtension.lowercased()
                guard mediaExts.contains(ext) || proxyExts.contains(ext) || techExts.contains(ext)
                        || u.lastPathComponent.lowercased().hasPrefix("fileinfo") else { continue }
                guard seen.insert(u.standardizedFileURL.path).inserted else { continue }
                files.append((u, Int64(v?.fileSize ?? 0), ext, u.deletingPathExtension().lastPathComponent,
                              u.deletingLastPathComponent().lastPathComponent.uppercased()))
            }
        }

        // Index des originaux : clé Insta360, clé GoPro, et « même nom sans extension »
        var instaOriginals = Set<String>()
        var instaLens0 = Set<String>()
        var goproOriginals = Set<String>()
        var stemOriginals = Set<String>()
        for f in files where mediaExts.contains(f.ext) {
            if let n = InstaName(f.stem), !n.isProxy {
                instaOriginals.insert(n.key)
                if n.lens == "0" { instaLens0.insert(n.key) }
            }
            if let g = goproKey(f.stem) { goproOriginals.insert(g) }
            stemOriginals.insert(f.url.deletingPathExtension().path.lowercased())
        }

        for f in files {
            let isMedia = mediaExts.contains(f.ext)
            if isMedia {
                r.totalBytes += f.size
                if videoExts.contains(f.ext) { r.videoCount += 1 }
            }

            // Fichiers vides / interrompus
            if isMedia && f.size < 4096 {
                r.items.append(CamItem(url: f.url, size: f.size, category: .empty,
                                       note: f.size == 0 ? "0 octet" : "\(f.size) octets", selected: true))
                continue
            }

            // Aperçus basse définition
            if proxyExts.contains(f.ext) || (InstaName(f.stem)?.isProxy ?? false && isMedia) {
                let hasOriginal: Bool = {
                    if let n = InstaName(f.stem) { return instaOriginals.contains(n.key) }
                    if let g = goproKey(f.stem) { return goproOriginals.contains(g) }
                    return stemOriginals.contains(f.url.deletingPathExtension().path.lowercased())
                }()
                r.items.append(CamItem(url: f.url, size: f.size, category: hasOriginal ? .proxies : .orphanProxies,
                                       note: hasOriginal ? "original présent" : "original introuvable",
                                       selected: hasOriginal))
                continue
            }

            // Vignettes, index, journaux
            if techExts.contains(f.ext) || f.url.lastPathComponent.lowercased().hasPrefix("fileinfo") {
                // Les sous-titres .SRT des drones DJI contiennent la télémétrie : on les garde s'ils accompagnent une vidéo
                if f.ext == "srt" && stemOriginals.contains(f.url.deletingPathExtension().path.lowercased()) { continue }
                r.items.append(CamItem(url: f.url, size: f.size, category: .technical,
                                       note: f.ext.uppercased(), selected: true))
                continue
            }

            guard isMedia else { continue }

            // Vidéo 360 incomplète : fichier de l'objectif « 1 » sans son fichier « 0 » (X3, X2, ONE X)
            if f.ext == "insv", let n = InstaName(f.stem), !n.isProxy, n.lens == "1", !instaLens0.contains(n.key) {
                r.items.append(CamItem(url: f.url, size: f.size, category: .incomplete,
                                       note: "fichier « _00_ » manquant", selected: false))
                continue
            }

            r.media.append(MediaItem(url: f.url, size: f.size, date: nil, isVideo: videoExts.contains(f.ext)))
        }
        return r
    }

    /// GoPro : GX010123 / GL010123 / GH010123 → « 010123 ».
    nonisolated static func goproKey(_ stem: String) -> String? {
        let s = stem.uppercased()
        guard s.count == 8, s.hasPrefix("G"), s.dropFirst(2).allSatisfy(\.isNumber) else { return nil }
        return String(s.dropFirst(2))
    }

    /// Durée d'une vidéo. Les .insv sont des MP4 : on passe par un lien temporaire en .mp4 pour AVFoundation.
    nonisolated static func duration(_ url: URL) async -> Double? {
        var target = url
        var link: URL?
        if ["insv", "360"].contains(url.pathExtension.lowercased()) {
            let l = FS.fm.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".mp4")
            if (try? FS.fm.createSymbolicLink(at: l, withDestinationURL: url)) != nil { target = l; link = l }
        }
        defer { if let link { try? FS.fm.removeItem(at: link) } }
        guard let d = try? await AVURLAsset(url: target).load(.duration), d.isNumeric else { return nil }
        let s = d.seconds
        return s.isFinite ? s : nil
    }

    // MARK: Sélection

    func toggle(_ id: UUID) {
        if let i = items.firstIndex(where: { $0.id == id }) { items[i].selected.toggle() }
    }

    func toggleCategory(_ c: CamCategory) {
        let on = !entries(in: c).allSatisfy(\.selected)
        for i in items.indices where items[i].category == c { items[i].selected = on }
    }

    // MARK: Suppression

    /// Supports externes : suppression définitive (la Corbeille n'y libère pas de place). Mac : Corbeille.
    func deleteSelected() async {
        guard !isDeleting else { return }
        isDeleting = true
        let targets = items.filter(\.selected)
        status = "Suppression de \(targets.count) fichier(s)…"
        let (freed, failed): (Int64, Int) = await Task.detached(priority: .userInitiated) {
            var freed: Int64 = 0, failed = 0
            for t in targets {
                let ok: Bool
                if t.url.path.hasPrefix("/Volumes/") {
                    ok = (try? FS.fm.removeItem(at: t.url)) != nil
                } else {
                    ok = FS.trash(t.url)
                }
                if ok { freed += t.size } else { failed += 1 }
            }
            return (freed, failed)
        }.value
        let gone = Set(targets.map(\.id))
        items.removeAll { gone.contains($0.id) && !FS.exists($0.url) }
        status = "\(Fmt.bytes(freed)) libérés" + (failed > 0 ? " · \(failed) fichier(s) protégé(s) non supprimé(s)" : "")
        isDeleting = false
    }
}
