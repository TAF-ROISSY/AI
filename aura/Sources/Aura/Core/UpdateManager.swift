import Foundation
import AppKit

enum UpdateSource: String {
    case sparkle = "Site de l'éditeur"
    case appStore = "App Store"
    case homebrew = "Homebrew"
}

struct AppUpdate: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let appURL: URL?
    let installed: String
    let available: String
    let source: UpdateSource
    let downloadURL: URL?
    let notesURL: URL?
    let storeID: Int?
    let brewName: String?
    var selected = true
}

/// Comparaison de versions « 1.10.2 » > « 1.9 ».
func versionIsNewer(_ a: String, than b: String) -> Bool {
    func parts(_ s: String) -> [Int] {
        s.split(whereSeparator: { !$0.isNumber }).compactMap { Int($0) }
    }
    let x = parts(a), y = parts(b)
    for i in 0..<max(x.count, y.count) {
        let l = i < x.count ? x[i] : 0, r = i < y.count ? y[i] : 0
        if l != r { return l > r }
    }
    return false
}

/// Lecture d'un flux Sparkle (appcast.xml) : on retient la version la plus récente.
final class AppcastParser: NSObject, XMLParserDelegate {
    struct Entry { var short = ""; var build = ""; var url: URL?; var notes: URL?; var minOS = "" }
    private var entries: [Entry] = []
    private var current: Entry?
    private var text = ""

    static func latest(_ data: Data) -> Entry? {
        let p = AppcastParser()
        let x = XMLParser(data: data)
        x.delegate = p
        x.parse()
        return p.entries.max { a, b in
            versionIsNewer(b.short.isEmpty ? b.build : b.short, than: a.short.isEmpty ? a.build : a.short)
        }
    }

    func parser(_ parser: XMLParser, didStartElement name: String, namespaceURI: String?,
                qualifiedName qName: String?, attributes: [String: String] = [:]) {
        text = ""
        if name == "item" { current = Entry() }
        if name == "enclosure", current != nil {
            if let s = attributes["sparkle:shortVersionString"] { current?.short = s }
            if let v = attributes["sparkle:version"] { current?.build = v }
            if let u = attributes["url"] { current?.url = URL(string: u) }
        }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) { text += string }

    func parser(_ parser: XMLParser, didEndElement name: String, namespaceURI: String?, qualifiedName qName: String?) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        switch name {
        case "sparkle:shortVersionString": current?.short = t
        case "sparkle:version": current?.build = t
        case "sparkle:releaseNotesLink", "sparkle:fullReleaseNotesLink": current?.notes = URL(string: t)
        case "sparkle:minimumSystemVersion": current?.minOS = t
        case "item":
            if let c = current, !(c.short.isEmpty && c.build.isEmpty) { entries.append(c) }
            current = nil
        default: break
        }
    }
}

@MainActor
final class UpdateManager: ObservableObject {
    @Published var updates: [AppUpdate] = []
    @Published var checked = 0
    @Published var total = 0
    @Published var isChecking = false
    @Published var macOSUpdates: [String] = []
    @Published var message = ""
    @Published var lastCheck: Date?
    @Published var busy: Set<UUID> = []

    nonisolated static var brewPath: String? {
        ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"].first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    func check() async {
        guard !isChecking else { return }
        isChecking = true
        updates = []
        message = ""
        let apps = await Task.detached { AppManager.scanApps() }.value
        total = apps.count
        checked = 0

        var found: [AppUpdate] = []
        // Vérifications réseau en parallèle, par petits paquets
        await withTaskGroup(of: AppUpdate?.self) { group in
            var index = 0
            while index < min(8, apps.count) {
                let app = apps[index]
                group.addTask { await Self.checkApp(app) }
                index += 1
            }
            while let r = await group.next() {
                checked += 1
                if let r { found.append(r) }
                if index < apps.count {
                    let app = apps[index]
                    group.addTask { await Self.checkApp(app) }
                    index += 1
                }
            }
        }
        found += await Task.detached { Self.checkHomebrew() }.value
        // Une app peut apparaître via Homebrew et Sparkle : on garde la première
        var seen = Set<String>()
        updates = found.filter { seen.insert($0.name.lowercased()).inserted }.sorted { $0.name < $1.name }
        macOSUpdates = await Task.detached {
            Shell.run("/usr/sbin/softwareupdate", ["-l"], timeout: 120).output
                .split(separator: "\n").filter { $0.contains("Title:") }
                .map { String($0).replacingOccurrences(of: "\t", with: " ").trimmingCharacters(in: .whitespaces) }
        }.value
        lastCheck = Date()
        isChecking = false
    }

    nonisolated static func checkApp(_ app: AppInfo) async -> AppUpdate? {
        guard let info = Bundle(url: app.url)?.infoDictionary,
              let installed = (info["CFBundleShortVersionString"] as? String) ?? (info["CFBundleVersion"] as? String) else { return nil }
        let build = info["CFBundleVersion"] as? String ?? installed

        // App Store : API publique de recherche d'Apple
        if FS.exists(app.url.appendingPathComponent("Contents/_MASReceipt/receipt")), let bid = app.bundleID,
           let u = URL(string: "https://itunes.apple.com/lookup?bundleId=\(bid)&country=fr&entity=macSoftware"),
           let resp = try? await URLSession.shared.data(from: u),
           let j = try? JSONSerialization.jsonObject(with: resp.0) as? [String: Any],
           let r = (j["results"] as? [[String: Any]])?.first,
           let v = r["version"] as? String {
            guard versionIsNewer(v, than: installed) else { return nil }
            return AppUpdate(name: app.name, appURL: app.url, installed: installed, available: v, source: .appStore,
                             downloadURL: nil, notesURL: (r["trackViewUrl"] as? String).flatMap(URL.init(string:)),
                             storeID: r["trackId"] as? Int, brewName: nil)
        }

        // Sparkle : flux déclaré dans l'Info.plist de l'app
        if let feed = (info["SUFeedURL"] as? String).flatMap(URL.init(string:)) {
            var req = URLRequest(url: feed, timeoutInterval: 15)
            req.setValue("Aura/1.0 Sparkle", forHTTPHeaderField: "User-Agent")
            guard let resp = try? await URLSession.shared.data(for: req),
                  let latest = AppcastParser.latest(resp.0) else { return nil }
            let newer = !latest.short.isEmpty ? versionIsNewer(latest.short, than: installed)
                                              : versionIsNewer(latest.build, than: build)
            guard newer else { return nil }
            return AppUpdate(name: app.name, appURL: app.url, installed: installed,
                             available: latest.short.isEmpty ? latest.build : latest.short, source: .sparkle,
                             downloadURL: latest.url, notesURL: latest.notes, storeID: nil, brewName: nil)
        }
        return nil
    }

    nonisolated static func checkHomebrew() -> [AppUpdate] {
        guard let brew = brewPath else { return [] }
        let out = Shell.run(brew, ["outdated", "--greedy", "--json=v2"], timeout: 180).output
        guard let start = out.firstIndex(of: "{"),
              let j = try? JSONSerialization.jsonObject(with: Data(out[start...].utf8)) as? [String: Any] else { return [] }
        var res: [AppUpdate] = []
        for c in (j["casks"] as? [[String: Any]]) ?? [] {
            guard let name = c["name"] as? String else { continue }
            res.append(AppUpdate(name: name, appURL: nil,
                                 installed: (c["installed_versions"] as? [String])?.first ?? "?",
                                 available: c["current_version"] as? String ?? "?", source: .homebrew,
                                 downloadURL: nil, notesURL: nil, storeID: nil, brewName: name))
        }
        for f in (j["formulae"] as? [[String: Any]]) ?? [] {
            guard let name = f["name"] as? String else { continue }
            res.append(AppUpdate(name: name + " (outil)", appURL: nil,
                                 installed: (f["installed_versions"] as? [String])?.first ?? "?",
                                 available: f["current_version"] as? String ?? "?", source: .homebrew,
                                 downloadURL: nil, notesURL: nil, storeID: nil, brewName: name))
        }
        return res
    }

    // MARK: Installation

    func toggle(_ id: UUID) {
        if let i = updates.firstIndex(where: { $0.id == id }) { updates[i].selected.toggle() }
    }

    func update(_ u: AppUpdate) async {
        busy.insert(u.id)
        defer { busy.remove(u.id) }
        switch u.source {
        case .appStore:
            let link = u.storeID.map { "macappstore://apps.apple.com/app/id\($0)" } ?? "macappstore://showUpdatesPage"
            if let url = URL(string: link) { NSWorkspace.shared.open(url) }
            message = "App Store ouvert sur \(u.name)"
        case .homebrew:
            guard let brew = Self.brewPath, let n = u.brewName else { return }
            let r = await Task.detached { Shell.run(brew, ["upgrade", n], timeout: 1800) }.value
            if r.status == 0 { updates.removeAll { $0.id == u.id }; message = "\(u.name) mis à jour" }
            else { message = "Échec de la mise à jour de \(u.name)" }
        case .sparkle:
            guard let dl = u.downloadURL else {
                if let app = u.appURL { NSWorkspace.shared.open(app) }
                return
            }
            message = "Téléchargement de \(u.name)…"
            do {
                let (tmp, _) = try await URLSession.shared.download(from: dl)
                let dest = FS.url("~/Downloads").appendingPathComponent(dl.lastPathComponent)
                try? FS.fm.removeItem(at: dest)
                try FS.fm.moveItem(at: tmp, to: dest)
                NSWorkspace.shared.open(dest)
                message = "\(u.name) \(u.available) téléchargé : suis l'installeur (ou glisse l'app dans Applications)."
            } catch {
                message = "Téléchargement impossible, ouverture de l'app pour qu'elle se mette à jour."
                if let app = u.appURL { NSWorkspace.shared.open(app) }
            }
        }
    }

    func updateSelected() async {
        for u in updates where u.selected { await update(u) }
    }

    func openMacOSUpdates() {
        if let u = URL(string: "x-apple.systempreferences:com.apple.Software-Update-Settings.extension") {
            NSWorkspace.shared.open(u)
        }
    }
}
