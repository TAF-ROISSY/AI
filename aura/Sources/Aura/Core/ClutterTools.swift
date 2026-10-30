import Foundation
import ImageIO
import CoreGraphics
import AppKit
import Security

// MARK: - Images similaires (empreinte perceptuelle dHash)

struct SimilarImage: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    let pixels: Int
    let date: Date?
    var selected = false
    var name: String { url.lastPathComponent }
}

struct SimilarGroup: Identifiable {
    let id = UUID()
    var images: [SimilarImage]
    var reclaimable: Int64 { images.filter(\.selected).reduce(0) { $0 + $1.size } }
}

@MainActor
final class SimilarImageFinder: ObservableObject {
    @Published var groups: [SimilarGroup] = []
    @Published var isBusy = false
    @Published var progress: Double = 0
    @Published var status = ""
    @Published var strictness: Double = 6     // distance de Hamming max (0 = identiques)

    nonisolated static let extensions: Set<String> = ["jpg", "jpeg", "png", "heic", "heif", "tif", "tiff", "gif", "webp", "bmp"]

    /// dHash 64 bits : compare la luminosité de pixels voisins sur une vignette 9×8.
    nonisolated static func dHash(_ url: URL) -> (UInt64, Int, Date?)? {
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
        let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any]
        let w = props?[kCGImagePropertyPixelWidth] as? Int ?? 0
        let h = props?[kCGImagePropertyPixelHeight] as? Int ?? 0
        let exif = props?[kCGImagePropertyExifDictionary] as? [CFString: Any]
        var date: Date?
        if let s = exif?[kCGImagePropertyExifDateTimeOriginal] as? String {
            let f = DateFormatter(); f.dateFormat = "yyyy:MM:dd HH:mm:ss"; date = f.date(from: s)
        }
        let opts: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true,
                                     kCGImageSourceThumbnailMaxPixelSize: 64,
                                     kCGImageSourceCreateThumbnailWithTransform: true]
        guard let thumb = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) else { return nil }
        var pixels = [UInt8](repeating: 0, count: 9 * 8)
        // Le contexte doit dessiner pendant que le tampon est garanti valide
        let drawn = pixels.withUnsafeMutableBytes { buf -> Bool in
            guard let ctx = CGContext(data: buf.baseAddress, width: 9, height: 8, bitsPerComponent: 8, bytesPerRow: 9,
                                      space: CGColorSpaceCreateDeviceGray(),
                                      bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return false }
            ctx.interpolationQuality = .medium
            ctx.draw(thumb, in: CGRect(x: 0, y: 0, width: 9, height: 8))
            return true
        }
        guard drawn else { return nil }
        var hash: UInt64 = 0
        var bit = 0
        for y in 0..<8 {
            for x in 0..<8 {
                if pixels[y * 9 + x] > pixels[y * 9 + x + 1] { hash |= (1 << UInt64(bit)) }
                bit += 1
            }
        }
        return (hash, w * h, date)
    }

    func scan(roots: [URL]) async {
        isBusy = true
        groups = []
        progress = 0
        status = "Recherche des images…"
        let threshold = Int(strictness)
        let result: [SimilarGroup] = await Task.detached(priority: .userInitiated) { [weak self] in
            // 1) inventaire
            var files: [(URL, Int64)] = []
            for root in roots {
                guard let e = FS.fm.enumerator(at: root, includingPropertiesForKeys: [.fileSizeKey, .isPackageKey, .isDirectoryKey],
                                               options: [.skipsHiddenFiles], errorHandler: { _, _ in true }) else { continue }
                for case let u as URL in e {
                    let v = try? u.resourceValues(forKeys: [.fileSizeKey, .isPackageKey, .isDirectoryKey])
                    if v?.isDirectory == true {
                        // On ne touche jamais aux bibliothèques Photos / Lightroom
                        if v?.isPackage == true || u.lastPathComponent == "Library" { e.skipDescendants() }
                        continue
                    }
                    if Self.extensions.contains(u.pathExtension.lowercased()), let s = v?.fileSize, s > 20_000 {
                        files.append((u, Int64(s)))
                    }
                }
            }
            // 2) empreintes
            var hashed: [(SimilarImage, UInt64)] = []
            for (i, f) in files.enumerated() {
                if let r = Self.dHash(f.0) {
                    hashed.append((SimilarImage(url: f.0, size: f.1, pixels: r.1, date: r.2), r.0))
                }
                if i % 25 == 0 {
                    let p = Double(i) / Double(max(1, files.count))
                    Task { @MainActor in self?.progress = p; self?.status = "Analyse visuelle \(i)/\(files.count)…" }
                }
            }
            // 3) regroupement (union-find)
            var parent = Array(0..<hashed.count)
            func find(_ x: Int) -> Int { var x = x; while parent[x] != x { parent[x] = parent[parent[x]]; x = parent[x] }; return x }
            for i in 0..<hashed.count {
                for j in (i + 1)..<hashed.count where (hashed[i].1 ^ hashed[j].1).nonzeroBitCount <= threshold {
                    let a = find(i), b = find(j)
                    if a != b { parent[a] = b }
                }
            }
            var buckets: [Int: [SimilarImage]] = [:]
            for i in 0..<hashed.count { buckets[find(i), default: []].append(hashed[i].0) }
            // 4) on garde la meilleure (plus haute définition, puis plus récente), on coche les autres
            return buckets.values.filter { $0.count > 1 }.map { imgs in
                let sorted = imgs.sorted { ($0.pixels, $0.size) > ($1.pixels, $1.size) }
                return SimilarGroup(images: sorted.enumerated().map { p in var x = p.element; x.selected = p.offset > 0; return x })
            }
            .sorted { $0.reclaimable > $1.reclaimable }
        }.value
        groups = result
        let total = result.reduce(Int64(0)) { $0 + $1.reclaimable }
        status = "\(result.count) séries d'images similaires · \(Fmt.bytes(total)) récupérables"
        progress = 1
        isBusy = false
    }

    func toggle(group: UUID, image: UUID) {
        guard let g = groups.firstIndex(where: { $0.id == group }),
              let i = groups[g].images.firstIndex(where: { $0.id == image }) else { return }
        groups[g].images[i].selected.toggle()
    }

    func removeSelected() async -> Int64 {
        var targets: [SimilarImage] = []
        for g in groups {
            let sel = g.images.filter(\.selected)
            if sel.count < g.images.count { targets += sel }     // toujours garder au moins une image
        }
        let freed = await Task.detached { targets.reduce(Int64(0)) { FS.trash($1.url) ? $0 + $1.size : $0 } }.value
        let gone = Set(targets.map(\.id))
        groups = groups.compactMap { g in
            var g = g; g.images.removeAll { gone.contains($0.id) }
            return g.images.count > 1 ? g : nil
        }
        return freed
    }
}

// MARK: - Nettoyage du cloud

struct CloudProvider: Identifiable {
    let id: String
    let name: String
    let icon: String
    let root: URL
    var logical: Int64 = 0       // taille totale des fichiers (en ligne + locale)
    var local: Int64 = 0         // ce qui occupe réellement le Mac
    var files: [CloudFile] = []
}

struct CloudFile: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let localSize: Int64
    let accessed: Date?
    var selected = false
}

@MainActor
final class CloudManager: ObservableObject {
    @Published var providers: [CloudProvider] = []
    @Published var isScanning = false
    @Published var message = ""

    nonisolated static func detect() -> [CloudProvider] {
        var out: [CloudProvider] = []
        let icloud = FS.url("~/Library/Mobile Documents/com~apple~CloudDocs")
        if FS.exists(icloud) { out.append(CloudProvider(id: "icloud", name: "iCloud Drive", icon: "icloud.fill", root: icloud)) }
        for dir in FS.children(FS.url("~/Library/CloudStorage"), hidden: false) {
            let n = dir.lastPathComponent
            let (name, icon): (String, String) =
                n.hasPrefix("GoogleDrive") ? ("Google Drive", "externaldrive.connected.to.line.below") :
                n.hasPrefix("OneDrive") ? ("OneDrive", "cloud.fill") :
                n.hasPrefix("Dropbox") ? ("Dropbox", "shippingbox.fill") :
                n.hasPrefix("Box") ? ("Box", "cube.fill") : (n, "cloud")
            let suffix = n.split(separator: "-", maxSplits: 1).dropFirst().first.map { " (\($0))" } ?? ""
            out.append(CloudProvider(id: n, name: name + suffix, icon: icon, root: dir))
        }
        if FS.exists(FS.url("~/Dropbox")) && !out.contains(where: { $0.name.hasPrefix("Dropbox") }) {
            out.append(CloudProvider(id: "dropbox", name: "Dropbox", icon: "shippingbox.fill", root: FS.url("~/Dropbox")))
        }
        return out
    }

    func scan() async {
        isScanning = true
        var list = await Task.detached { Self.detect() }.value
        for i in list.indices {
            let root = list[i].root
            let r = await Task.detached { Self.measure(root) }.value
            list[i].logical = r.0
            list[i].local = r.1
            list[i].files = r.2
        }
        providers = list
        isScanning = false
    }

    nonisolated static func measure(_ root: URL) -> (Int64, Int64, [CloudFile]) {
        let keys: [URLResourceKey] = [.fileSizeKey, .totalFileAllocatedSizeKey, .isRegularFileKey, .contentAccessDateKey]
        guard let e = FS.fm.enumerator(at: root, includingPropertiesForKeys: keys, options: [.skipsHiddenFiles],
                                       errorHandler: { _, _ in true }) else { return (0, 0, []) }
        var logical: Int64 = 0, local: Int64 = 0
        var files: [CloudFile] = []
        for case let u as URL in e {
            guard let v = try? u.resourceValues(forKeys: Set(keys)), v.isRegularFile == true else { continue }
            let size = Int64(v.fileSize ?? 0)
            let onDisk = Int64(v.totalFileAllocatedSize ?? 0)
            logical += size
            local += onDisk
            if onDisk > 1_000_000 { files.append(CloudFile(url: u, localSize: onDisk, accessed: v.contentAccessDate)) }
        }
        // Les plus gros et les moins consultés en premier
        return (logical, local, files.sorted { $0.localSize > $1.localSize }.prefix(500).map { $0 })
    }

    func toggle(provider: String, file: UUID) {
        guard let p = providers.firstIndex(where: { $0.id == provider }),
              let f = providers[p].files.firstIndex(where: { $0.id == file }) else { return }
        providers[p].files[f].selected.toggle()
    }

    func selectUnused(provider: String, days: Int = 90) {
        guard let p = providers.firstIndex(where: { $0.id == provider }) else { return }
        let limit = Date().addingTimeInterval(-Double(days) * 86400)
        for f in providers[p].files.indices {
            providers[p].files[f].selected = (providers[p].files[f].accessed ?? .distantPast) < limit
        }
    }

    /// Libère l'espace local : le fichier reste dans le cloud, il se retélécharge à l'ouverture.
    func evictSelected(provider: String) async {
        guard let p = providers.firstIndex(where: { $0.id == provider }) else { return }
        let targets = providers[p].files.filter(\.selected)
        let freed = await Task.detached { () -> Int64 in
            var freed: Int64 = 0
            for f in targets {
                var ok = (try? FS.fm.evictUbiquitousItem(at: f.url)) != nil
                if !ok { ok = Shell.run("/usr/bin/fileproviderctl", ["evict", f.url.path], timeout: 60).status == 0 }
                if !ok { ok = Shell.run("/usr/bin/brctl", ["evict", f.url.path], timeout: 60).status == 0 }
                if ok { freed += f.localSize }
            }
            return freed
        }.value
        message = "\(Fmt.bytes(freed)) libérés sur le Mac (fichiers toujours disponibles dans le cloud)"
        await scan()
    }

    /// Supprime pour de bon (du Mac ET du cloud, via la Corbeille).
    func deleteSelected(provider: String) async {
        guard let p = providers.firstIndex(where: { $0.id == provider }) else { return }
        let targets = providers[p].files.filter(\.selected)
        let n = await Task.detached { targets.filter { FS.trash($0.url) }.count }.value
        message = "\(n) fichier(s) envoyés à la Corbeille (et retirés du cloud)"
        await scan()
    }
}

// MARK: - Broyeur

enum Shredder {
    /// Écrase le contenu avec des données aléatoires, renomme, puis supprime.
    static func shred(_ url: URL, passes: Int) -> Bool {
        var isDir: ObjCBool = false
        guard FS.fm.fileExists(atPath: url.path, isDirectory: &isDir) else { return false }
        if isDir.boolValue {
            let ok = FS.children(url).map { shred($0, passes: passes) }.allSatisfy { $0 }
            return ok && (try? FS.fm.removeItem(at: url)) != nil
        }
        let size = Int((try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
        if let h = try? FileHandle(forWritingTo: url) {
            let chunk = 1 << 20
            for _ in 0..<max(1, passes) {
                try? h.seek(toOffset: 0)
                var written = 0
                while written < size {
                    let n = min(chunk, size - written)
                    var bytes = [UInt8](repeating: 0, count: n)
                    _ = SecRandomCopyBytes(kSecRandomDefault, n, &bytes)
                    h.write(Data(bytes))
                    written += n
                }
                try? h.synchronize()
            }
            try? h.truncate(atOffset: 0)
            try? h.close()
        }
        let renamed = url.deletingLastPathComponent().appendingPathComponent(UUID().uuidString)
        let target = (try? FS.fm.moveItem(at: url, to: renamed)) != nil ? renamed : url
        return (try? FS.fm.removeItem(at: target)) != nil
    }
}
