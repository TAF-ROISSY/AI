import Foundation
import AppKit
import ImageIO
import AVFoundation
import CryptoKit

// MARK: - Programme du voyage (même principe que Prisme)

/// Une étape : à partir de cette date (et heure), tu es à ce lieu, jusqu'à l'étape suivante.
struct TripStage: Identifiable, Codable, Hashable {
    var id = UUID()
    var place: String
    var start: Date
}

struct Trip: Identifiable, Codable, Hashable {
    var id = UUID()
    var name: String                    // dossier principal : « Thaïlande »
    var stages: [TripStage]
    var end: Date                       // fin du voyage
    var timeZoneID: String              // fuseau du pays visité

    var timeZone: TimeZone { TimeZone(identifier: timeZoneID) ?? .current }
    var sortedStages: [TripStage] {
        stages.filter { !$0.place.trimmingCharacters(in: .whitespaces).isEmpty }.sorted { $0.start < $1.start }
    }
}

enum SubfolderMode: String, CaseIterable, Identifiable, Codable {
    case byDay = "Un sous-dossier par jour (Bangkok 1, Bangkok 2…)"
    case byVisit = "Un sous-dossier par passage dans la ville"
    case none = "Pas de sous-dossier (tout dans la ville)"
    var id: String { rawValue }
}

enum DuplicateAction: String, CaseIterable, Identifiable, Codable {
    case setAside = "Les mettre de côté dans « Doublons »"
    case leave = "Les laisser à leur place"
    case trash = "Les mettre à la Corbeille"
    var id: String { rawValue }
}

enum TransferMode: String, CaseIterable, Identifiable, Codable {
    case move = "Déplacer (ranger le support lui-même)"
    case copy = "Copier (les originaux restent en place)"
    var id: String { rawValue }
}

// MARK: - Plan

struct MediaItem: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    let date: Date?
    let isVideo: Bool
}

struct PlannedFile: Identifiable, Hashable {
    let id = UUID()
    let source: URL
    let destination: URL
    let isVideo: Bool
    let date: Date?
}

struct PlannedFolder: Identifiable, Hashable {
    var id: String { path }
    let path: String          // relatif au dossier du voyage : « Bangkok/Bangkok 1 »
    var files: [PlannedFile]
    var photos: Int { files.filter { !$0.isVideo }.count }
    var videos: Int { files.filter(\.isVideo).count }
    var firstDate: Date? { files.compactMap(\.date).min() }
}

struct OrganizePlan {
    var folders: [PlannedFolder] = []
    var duplicates: [(original: URL, copy: URL)] = []
    var outside: [MediaItem] = []        // prises hors des dates du voyage
    var undated: [MediaItem] = []
    var tripRoot: URL?
    var totalFiles: Int { folders.reduce(0) { $0 + $1.files.count } }
}

struct TransferRecord: Codable {
    let from: String
    let to: String
    let copied: Bool
}

// MARK: - Moteur

@MainActor
final class PhotoOrganizer: ObservableObject {
    @Published var trips: [Trip] = []
    @Published var current: Trip
    @Published var sources: [URL] = []
    @Published var destination: URL?
    @Published var subfolders: SubfolderMode = .byDay
    @Published var rename = true
    @Published var separateVideos = false
    @Published var duplicateAction: DuplicateAction = .setAside
    @Published var transfer: TransferMode = .move
    @Published var includeOutside = false

    @Published var plan: OrganizePlan?
    @Published var isWorking = false
    @Published var progress: Double = 0
    @Published var status = ""
    @Published var lastBatch: [TransferRecord] = []

    nonisolated static let photoExts: Set<String> = ["jpg", "jpeg", "heic", "heif", "png", "tif", "tiff", "gif", "webp",
                                                     "dng", "cr2", "cr3", "nef", "arw", "raf", "orf", "rw2", "srw"]
    nonisolated static let videoExts: Set<String> = ["mov", "mp4", "m4v", "avi", "mts", "m2ts", "mkv", "3gp", "insv", "lrv"]

    private var storeDir: URL {
        let d = FS.url("~/Library/Application Support/Aura")
        try? FS.fm.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }

    init() {
        let cal = Calendar.current
        let start = cal.startOfDay(for: Date())
        current = Trip(name: "Mon voyage",
                       stages: [TripStage(place: "", start: start)],
                       end: cal.date(byAdding: .day, value: 7, to: start) ?? start,
                       timeZoneID: TimeZone.current.identifier)
        if let d = try? Data(contentsOf: storeDir.appendingPathComponent("voyages.json")),
           let t = try? JSONDecoder().decode([Trip].self, from: d) {
            trips = t
            if let last = t.last { current = last }
        }
        if let d = try? Data(contentsOf: storeDir.appendingPathComponent("classement-annulation.json")),
           let r = try? JSONDecoder().decode([TransferRecord].self, from: d) {
            lastBatch = r
        }
    }

    // MARK: Programme

    func saveTrip() {
        if let i = trips.firstIndex(where: { $0.id == current.id }) { trips[i] = current } else { trips.append(current) }
        if let d = try? JSONEncoder().encode(trips) { try? d.write(to: storeDir.appendingPathComponent("voyages.json")) }
    }

    func newTrip() {
        saveTrip()
        let start = Calendar.current.startOfDay(for: Date())
        current = Trip(name: "Nouveau voyage", stages: [TripStage(place: "", start: start)],
                       end: Calendar.current.date(byAdding: .day, value: 7, to: start) ?? start,
                       timeZoneID: current.timeZoneID)
        plan = nil
    }

    func deleteTrip(_ t: Trip) {
        trips.removeAll { $0.id == t.id }
        if let d = try? JSONEncoder().encode(trips) { try? d.write(to: storeDir.appendingPathComponent("voyages.json")) }
        if current.id == t.id { newTrip() }
    }

    func addStage() {
        let last = current.sortedStages.last?.start ?? current.end
        let next = Calendar.current.date(byAdding: .day, value: 1, to: last) ?? last
        current.stages.append(TripStage(place: "", start: next))
    }

    var suggestedDestination: URL {
        if let d = destination { return d }
        if let s = sources.first, s.path.hasPrefix("/Volumes/") {
            let comps = s.pathComponents
            if comps.count >= 3 { return URL(fileURLWithPath: "/Volumes/\(comps[2])/Voyages") }
        }
        return FS.url("~/Pictures/Voyages")
    }

    // MARK: Analyse

    func analyze() async {
        guard !isWorking, !sources.isEmpty else { return }
        let trip = current
        guard !trip.sortedStages.isEmpty else { status = "Ajoute au moins une étape avec un lieu."; return }
        saveTrip()
        isWorking = true
        progress = 0
        plan = nil
        status = "Recherche des photos et vidéos…"
        let roots = sources
        let tripRoot = suggestedDestination.appendingPathComponent(Self.safeName(trip.name))
        let options = (subfolders, rename, separateVideos, includeOutside)

        // 1. Inventaire
        let files = await Task.detached(priority: .userInitiated) {
            Self.listMedia(roots: roots, excluding: tripRoot)
        }.value
        status = "Lecture des dates de prise de vue (\(files.count) fichiers)…"

        // 2. Dates (EXIF pour les photos, métadonnées pour les vidéos)
        var items: [MediaItem] = []
        items.reserveCapacity(files.count)
        for (i, f) in files.enumerated() {
            let date = await Self.captureDate(f.url, isVideo: f.isVideo, tz: trip.timeZone)
            items.append(MediaItem(url: f.url, size: f.size, date: date, isVideo: f.isVideo))
            if i % 20 == 0 { progress = 0.6 * Double(i) / Double(max(1, files.count)) }
        }
        // Live Photos : la vidéo prend la date de la photo du même nom
        items = Self.pairLivePhotos(items)

        // 3. Doublons
        status = "Recherche des doublons…"
        let dupes = await Task.detached(priority: .userInitiated) { Self.findDuplicates(items) }.value
        progress = 0.85

        // 4. Plan de classement
        status = "Préparation du classement…"
        let duplicateSet = Set(dupes.map(\.copy))
        let p = await Task.detached(priority: .userInitiated) {
            Self.makePlan(items: items.filter { !duplicateSet.contains($0.url) }, trip: trip, tripRoot: tripRoot,
                          mode: options.0, rename: options.1, separateVideos: options.2, includeOutside: options.3)
        }.value
        var full = p
        full.duplicates = dupes
        plan = full
        progress = 1
        status = "\(full.totalFiles) fichier(s) à classer dans \(full.folders.count) dossier(s)"
            + (dupes.isEmpty ? "" : " · \(dupes.count) doublon(s)")
        isWorking = false
    }

    nonisolated static func listMedia(roots: [URL], excluding: URL) -> [(url: URL, size: Int64, isVideo: Bool)] {
        var out: [(URL, Int64, Bool)] = []
        var seen = Set<String>()
        let excl = excluding.standardizedFileURL.path
        for root in roots {
            guard let e = FS.fm.enumerator(at: root, includingPropertiesForKeys: [.fileSizeKey, .isDirectoryKey, .isPackageKey],
                                           options: [.skipsHiddenFiles], errorHandler: { _, _ in true }) else { continue }
            for case let u as URL in e {
                let path = u.standardizedFileURL.path
                let v = try? u.resourceValues(forKeys: [.fileSizeKey, .isDirectoryKey, .isPackageKey])
                if v?.isDirectory == true {
                    // Ne jamais entrer dans le dossier de destination ni dans les bibliothèques (Photos, Lightroom…)
                    if path == excl || path.hasPrefix(excl + "/") || v?.isPackage == true { e.skipDescendants() }
                    continue
                }
                let ext = u.pathExtension.lowercased()
                let isPhoto = photoExts.contains(ext), isVideo = videoExts.contains(ext)
                guard isPhoto || isVideo, seen.insert(path).inserted else { continue }
                out.append((u, Int64(v?.fileSize ?? 0), isVideo))
            }
        }
        return out.map { (url: $0.0, size: $0.1, isVideo: $0.2) }
    }

    /// Date de prise de vue : EXIF (photo) ou métadonnées (vidéo), sinon date du fichier.
    nonisolated static func captureDate(_ url: URL, isVideo: Bool, tz: TimeZone) async -> Date? {
        if !isVideo, let src = CGImageSourceCreateWithURL(url as CFURL, nil),
           let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any] {
            let exif = props[kCGImagePropertyExifDictionary] as? [CFString: Any]
            let tiff = props[kCGImagePropertyTIFFDictionary] as? [CFString: Any]
            if let raw = (exif?[kCGImagePropertyExifDateTimeOriginal] as? String)
                ?? (exif?[kCGImagePropertyExifDateTimeDigitized] as? String)
                ?? (tiff?[kCGImagePropertyTIFFDateTime] as? String) {
                let f = DateFormatter()
                f.locale = Locale(identifier: "en_US_POSIX")
                // Avec décalage horaire enregistré (iPhone récent) : date exacte ; sinon heure locale du voyage
                if let off = exif?["OffsetTimeOriginal" as CFString] as? String {
                    f.dateFormat = "yyyy:MM:dd HH:mm:ssXXX"
                    if let d = f.date(from: raw + off) { return d }
                }
                f.dateFormat = "yyyy:MM:dd HH:mm:ss"
                f.timeZone = tz
                if let d = f.date(from: raw) { return d }
            }
        }
        if isVideo {
            let asset = AVURLAsset(url: url)
            if let item = try? await asset.load(.creationDate), let d = try? await item.load(.dateValue) {
                return d
            }
        }
        let v = try? url.resourceValues(forKeys: [.creationDateKey, .contentModificationDateKey])
        return v?.creationDate ?? v?.contentModificationDate
    }

    nonisolated static func pairLivePhotos(_ items: [MediaItem]) -> [MediaItem] {
        var photoDates: [String: Date] = [:]
        for i in items where !i.isVideo {
            if let d = i.date { photoDates[i.url.deletingPathExtension().path] = d }
        }
        return items.map { i in
            guard i.isVideo, let d = photoDates[i.url.deletingPathExtension().path] else { return i }
            return MediaItem(url: i.url, size: i.size, date: d, isVideo: true)
        }
    }

    // MARK: Doublons

    nonisolated static func partialHash(_ url: URL, size: Int64) -> String? {
        guard let h = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? h.close() }
        var hasher = SHA256()
        if let a = try? h.read(upToCount: 1 << 20) { hasher.update(data: a) }
        if size > 2 << 20 {
            try? h.seek(toOffset: UInt64(size - (1 << 20)))
            if let b = try? h.read(upToCount: 1 << 20) { hasher.update(data: b) }
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    nonisolated static func fullHash(_ url: URL) -> String? {
        guard let h = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? h.close() }
        var hasher = SHA256()
        while let chunk = try? h.read(upToCount: 4 << 20), !chunk.isEmpty { hasher.update(data: chunk) }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    /// Doublons au contenu identique : on garde le fichier au nom le plus court (souvent l'original).
    nonisolated static func findDuplicates(_ items: [MediaItem]) -> [(original: URL, copy: URL)] {
        var result: [(URL, URL)] = []
        for group in Dictionary(grouping: items, by: \.size).values where group.count > 1 {
            for partial in Dictionary(grouping: group, by: { partialHash($0.url, size: $0.size) ?? UUID().uuidString }).values
            where partial.count > 1 {
                for same in Dictionary(grouping: partial, by: { fullHash($0.url) ?? UUID().uuidString }).values where same.count > 1 {
                    let sorted = same.sorted { ($0.url.lastPathComponent.count, $0.url.path) < ($1.url.lastPathComponent.count, $1.url.path) }
                    for c in sorted.dropFirst() { result.append((sorted[0].url, c.url)) }
                }
            }
        }
        return result.map { (original: $0.0, copy: $0.1) }
    }

    // MARK: Classement

    nonisolated static func safeName(_ s: String) -> String {
        let cleaned = s.trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "/", with: "-").replacingOccurrences(of: ":", with: "-")
        return cleaned.isEmpty ? "Voyage" : cleaned
    }

    nonisolated static func makePlan(items: [MediaItem], trip: Trip, tripRoot: URL, mode: SubfolderMode,
                                     rename: Bool, separateVideos: Bool, includeOutside: Bool) -> OrganizePlan {
        var plan = OrganizePlan()
        plan.tripRoot = tripRoot
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = trip.timeZone
        let stages = trip.sortedStages
        guard let first = stages.first else { return plan }

        // Numérotation des jours / passages par ville (une ville revisitée continue sa numérotation)
        var dayKeys: [String: [Date]] = [:]          // ville -> jours distincts
        var visitIndex: [UUID: Int] = [:]
        var visitsPerPlace: [String: Int] = [:]
        for s in stages {
            let key = safeName(s.place)
            visitsPerPlace[key, default: 0] += 1
            visitIndex[s.id] = visitsPerPlace[key]
        }

        var buckets: [String: [MediaItem]] = [:]
        for item in items {
            guard let d = item.date else { plan.undated.append(item); continue }
            guard d >= first.start, d < trip.end else {
                if includeOutside { buckets["Autres dates", default: []].append(item) } else { plan.outside.append(item) }
                continue
            }
            let stage = stages.last(where: { $0.start <= d }) ?? first
            let city = safeName(stage.place)
            var folder = city
            switch mode {
            case .byDay:
                let day = cal.startOfDay(for: d)
                if !(dayKeys[city]?.contains(day) ?? false) { dayKeys[city, default: []].append(day) }
                folder = "\(city)/__DAY__\(day.timeIntervalSince1970)"
            case .byVisit:
                folder = "\(city)/\(city) \(visitIndex[stage.id] ?? 1)"
            case .none:
                break
            }
            buckets[folder, default: []].append(item)
        }

        // Les jours deviennent « Bangkok 1, Bangkok 2… » dans l'ordre chronologique
        var finalBuckets: [String: [MediaItem]] = [:]
        for (key, list) in buckets {
            if let r = key.range(of: "/__DAY__") {
                let city = String(key[..<r.lowerBound])
                let ts = Double(key[r.upperBound...]) ?? 0
                let days = (dayKeys[city] ?? []).sorted()
                let n = (days.firstIndex(of: Date(timeIntervalSince1970: ts)) ?? 0) + 1
                finalBuckets["\(city)/\(city) \(n)", default: []].append(contentsOf: list)
            } else {
                finalBuckets[key, default: []].append(contentsOf: list)
            }
        }

        for (rel, list) in finalBuckets {
            let sorted = list.sorted { ($0.date ?? .distantPast, $0.url.path) < ($1.date ?? .distantPast, $1.url.path) }
            let baseName = (rel as NSString).lastPathComponent
            var counter = 0
            var numberFor: [String: Int] = [:]      // Live Photos : même numéro pour la photo et sa vidéo
            var files: [PlannedFile] = []
            for item in sorted {
                var dir = tripRoot.appendingPathComponent(rel)
                if separateVideos && item.isVideo { dir = dir.appendingPathComponent("Vidéos") }
                let ext = item.url.pathExtension
                let name: String
                if rename {
                    let stem = item.url.deletingPathExtension().path
                    let n: Int
                    if let existing = numberFor[stem] { n = existing } else { counter += 1; n = counter; numberFor[stem] = n }
                    name = String(format: "%@ - %03d.%@", baseName, n, ext.lowercased())
                } else {
                    name = item.url.lastPathComponent
                }
                files.append(PlannedFile(source: item.url, destination: dir.appendingPathComponent(name),
                                         isVideo: item.isVideo, date: item.date))
            }
            plan.folders.append(PlannedFolder(path: rel, files: files))
        }
        plan.folders.sort { ($0.firstDate ?? .distantFuture, $0.path) < ($1.firstDate ?? .distantFuture, $1.path) }
        return plan
    }

    // MARK: Exécution

    func apply() async {
        guard let plan, let tripRoot = plan.tripRoot, !isWorking else { return }
        isWorking = true
        progress = 0
        status = transfer == .move ? "Classement en cours…" : "Copie en cours…"
        let copy = transfer == .copy
        let dupAction = duplicateAction
        let all = plan.folders.flatMap(\.files)
        let dupes = plan.duplicates

        let records: [TransferRecord] = await Task.detached(priority: .userInitiated) { [weak self] in
            var done: [TransferRecord] = []
            let total = Double(max(1, all.count + dupes.count))
            for (i, f) in all.enumerated() {
                if let dst = Self.transfer(f.source, to: f.destination, copy: copy) {
                    done.append(TransferRecord(from: f.source.path, to: dst.path, copied: copy))
                }
                if i % 10 == 0 { Task { @MainActor in self?.progress = Double(i) / total } }
            }
            // Doublons
            for d in dupes {
                switch dupAction {
                case .setAside:
                    let dst = tripRoot.appendingPathComponent("Doublons").appendingPathComponent(d.copy.lastPathComponent)
                    if let r = Self.transfer(d.copy, to: dst, copy: false) {
                        done.append(TransferRecord(from: d.copy.path, to: r.path, copied: false))
                    }
                case .trash:
                    _ = FS.trash(d.copy)
                case .leave:
                    break
                }
            }
            return done
        }.value

        lastBatch = records
        if let d = try? JSONEncoder().encode(records) {
            try? d.write(to: storeDir.appendingPathComponent("classement-annulation.json"))
        }
        progress = 1
        status = "\(records.count) fichier(s) \(copy ? "copiés" : "classés") dans \(tripRoot.lastPathComponent)."
        self.plan = nil
        isWorking = false
        NSWorkspace.shared.activateFileViewerSelecting([tripRoot])
    }

    /// Déplace ou copie sans jamais écraser (« Bangkok 1 - 001 2.jpg » si le nom existe déjà).
    nonisolated static func transfer(_ src: URL, to wanted: URL, copy: Bool) -> URL? {
        guard FS.exists(src) else { return nil }
        try? FS.fm.createDirectory(at: wanted.deletingLastPathComponent(), withIntermediateDirectories: true)
        var dst = wanted
        let stem = wanted.deletingPathExtension().lastPathComponent, ext = wanted.pathExtension
        var n = 2
        while FS.exists(dst) {
            dst = wanted.deletingLastPathComponent().appendingPathComponent(ext.isEmpty ? "\(stem) \(n)" : "\(stem) \(n).\(ext)")
            n += 1
        }
        do {
            if copy { try FS.fm.copyItem(at: src, to: dst) } else { try FS.fm.moveItem(at: src, to: dst) }
            return dst
        } catch {
            return nil
        }
    }

    func undo() async {
        guard !lastBatch.isEmpty, !isWorking else { return }
        isWorking = true
        status = "Annulation…"
        let batch = lastBatch
        let restored = await Task.detached(priority: .userInitiated) { () -> Int in
            var n = 0
            for r in batch.reversed() {
                let to = URL(fileURLWithPath: r.to)
                if r.copied {
                    if (try? FS.fm.removeItem(at: to)) != nil { n += 1 }
                } else if Self.transfer(to, to: URL(fileURLWithPath: r.from), copy: false) != nil {
                    n += 1
                }
            }
            // Dossiers devenus vides
            let dirs = Set(batch.map { URL(fileURLWithPath: $0.to).deletingLastPathComponent().path })
                .sorted { $0.count > $1.count }
            for d in dirs {
                let u = URL(fileURLWithPath: d)
                if FS.children(u).filter({ $0.lastPathComponent != ".DS_Store" }).isEmpty { try? FS.fm.removeItem(at: u) }
            }
            return n
        }.value
        lastBatch = []
        try? FS.fm.removeItem(at: storeDir.appendingPathComponent("classement-annulation.json"))
        status = "\(restored) fichier(s) remis à leur place d'origine."
        isWorking = false
    }
}
