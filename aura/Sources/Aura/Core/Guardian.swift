import Foundation
import AppKit

/// Événement détecté par la protection en temps réel.
struct GuardEvent: Identifiable {
    enum Kind { case launchItem, download }
    enum Level: Int { case ok, info, warning, danger }

    let id = UUID()
    let date = Date()
    let kind: Kind
    let url: URL
    let title: String
    var detail: String
    var level: Level
    var origin: String?
    var launchLabel: String?
    var handled = false
}

/// Protection en temps réel : surveille les dossiers de lancement automatique et
/// le dossier Téléchargements, et analyse chaque nouvel élément dès son arrivée.
@MainActor
final class Guardian: ObservableObject {
    @Published var events: [GuardEvent] = []
    @Published var isActive = false

    @Pref("aura.guard.enabled") var enabled = true
    @Pref("aura.guard.downloads") var watchDownloads = true

    private var sources: [DispatchSourceFileSystemObject] = []
    private var snapshots: [String: Set<String>] = [:]
    private var pending: Set<String> = []
    private weak var health: HealthCenter?

    private static let launchDirs = ["~/Library/LaunchAgents", "/Library/LaunchAgents", "/Library/LaunchDaemons"].map(FS.url)
    private static var downloadsDir: URL { FS.url("~/Downloads") }
    private static let partialExtensions: Set<String> = ["download", "crdownload", "part", "partial", "opdownload", "tmp"]
    private static let watchedTypes: Set<String> = ["dmg", "pkg", "mpkg", "app", "zip", "command", "sh", "terminal", "xip"]

    var unhandledCount: Int { events.filter { !$0.handled && $0.level.rawValue >= GuardEvent.Level.warning.rawValue }.count }

    func start(health: HealthCenter) {
        self.health = health
        guard enabled, sources.isEmpty else { return }
        var dirs = Self.launchDirs
        if watchDownloads { dirs.append(Self.downloadsDir) }
        for dir in dirs where FS.exists(dir) {
            snapshots[dir.path] = Set(FS.children(dir).map(\.lastPathComponent))
            let fd = open(dir.path, O_EVTONLY)
            guard fd >= 0 else { continue }
            let src = DispatchSource.makeFileSystemObjectSource(fileDescriptor: fd, eventMask: [.write, .rename, .link], queue: .main)
            src.setEventHandler { [weak self] in
                Task { @MainActor in self?.directoryChanged(dir) }
            }
            src.setCancelHandler { close(fd) }
            src.resume()
            sources.append(src)
        }
        isActive = !sources.isEmpty
    }

    func stop() {
        sources.forEach { $0.cancel() }
        sources = []
        isActive = false
    }

    func restart() {
        stop()
        if let h = health { start(health: h) }
    }

    // MARK: Détection

    private func directoryChanged(_ dir: URL) {
        let now = Set(FS.children(dir).map(\.lastPathComponent))
        let before = snapshots[dir.path] ?? []
        snapshots[dir.path] = now
        for name in now.subtracting(before) {
            let url = dir.appendingPathComponent(name)
            if dir == Self.downloadsDir {
                considerDownload(url)
            } else if url.pathExtension == "plist" {
                Task { await analyzeLaunchItem(url) }
            }
        }
    }

    private func considerDownload(_ url: URL) {
        let ext = url.pathExtension.lowercased()
        guard !Self.partialExtensions.contains(ext), Self.watchedTypes.contains(ext),
              !pending.contains(url.path) else { return }
        pending.insert(url.path)
        Task {
            // On attend que le téléchargement soit complet (taille stable)
            var last: Int64 = -1
            for _ in 0..<120 {
                let s = FS.size(of: url)
                if s > 0 && s == last { break }
                last = s
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
            await analyzeDownload(url)
            pending.remove(url.path)
        }
    }

    // MARK: Analyse

    private func analyzeLaunchItem(_ url: URL) async {
        // Laisse le temps à l'installeur d'écrire complètement le fichier
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        let item = await Task.detached { () -> (String, String, [String], GuardEvent.Level) in
            let dict = NSDictionary(contentsOf: url) as? [String: Any] ?? [:]
            let label = dict["Label"] as? String ?? url.deletingPathExtension().lastPathComponent
            let prog = (dict["Program"] as? String) ?? (dict["ProgramArguments"] as? [String])?.first ?? "—"
            var reasons: [String] = []
            var level = GuardEvent.Level.info
            if SecurityScanner.matchKnown(label + " " + prog) != nil {
                reasons.append("logiciel indésirable connu"); level = .danger
            }
            let progURL = URL(fileURLWithPath: prog)
            if progURL.pathComponents.contains(where: { $0.hasPrefix(".") && $0 != "." }) {
                reasons.append("programme caché"); level = .danger
            }
            if ["/tmp/", "/private/tmp/", "/Users/Shared/", "/var/tmp/"].contains(where: { prog.hasPrefix($0) }) {
                reasons.append("programme dans un dossier temporaire"); level = .danger
            }
            if FS.exists(progURL) {
                let (sig, _) = CodeSign.status(of: progURL)
                if sig.isSuspicious { reasons.append("programme \(sig.rawValue.lowercased())"); if level.rawValue < 2 { level = .warning } }
            }
            return (label, prog, reasons, level)
        }.value
        let detail = (item.2.isEmpty ? "Nouveau lancement automatique" : item.2.joined(separator: " · ").capitalizedFirst)
            + " — " + item.1
        let ev = GuardEvent(kind: .launchItem, url: url, title: item.0, detail: detail, level: item.3,
                            origin: nil, launchLabel: item.0)
        push(ev)
        health?.notify(item.3 == .danger ? "⚠️ Lancement automatique suspect" : "Nouveau lancement automatique",
                       "\(item.0) s'est installé pour démarrer tout seul. Vérifie-le dans Aura › Sécurité.")
    }

    private func analyzeDownload(_ url: URL) async {
        guard FS.exists(url) else { return }
        let r = await Task.detached { Self.assess(url) }.value
        push(GuardEvent(kind: .download, url: url, title: url.lastPathComponent, detail: r.detail,
                        level: r.level, origin: r.origin))
        if r.level.rawValue >= GuardEvent.Level.warning.rawValue {
            health?.notify(r.level == .danger ? "⚠️ Téléchargement dangereux" : "Téléchargement à vérifier",
                           "\(url.lastPathComponent) : \(r.detail)")
        }
    }

    /// Verdict de Gatekeeper + provenance + liste noire.
    nonisolated static func assess(_ url: URL) -> (level: GuardEvent.Level, detail: String, origin: String?) {
        let ext = url.pathExtension.lowercased()
        let froms = Shell.run("/usr/bin/mdls", ["-raw", "-name", "kMDItemWhereFroms", url.path], timeout: 10).output
        let origin = froms.components(separatedBy: "\"").dropFirst().first { $0.hasPrefix("http") }

        if let k = SecurityScanner.matchKnown(url.lastPathComponent + " " + (origin ?? "")) {
            return (.danger, k == .adware ? "Logiciel publicitaire connu" : "Application réputée indésirable", origin)
        }
        if ["zip", "command", "sh", "terminal", "xip"].contains(ext) {
            if ["command", "sh", "terminal"].contains(ext) {
                return (.warning, "Script exécutable : ne l'ouvre que si tu connais sa source", origin)
            }
            return (.ok, "Archive téléchargée", origin)
        }
        let type: [String]
        switch ext {
        case "pkg", "mpkg": type = ["--type", "install"]
        case "dmg": type = ["--type", "open", "--context", "context:primary-signature"]
        default: type = ["--type", "execute"]
        }
        let r = Shell.run("/usr/sbin/spctl", ["--assess", "-vv"] + type + [url.path], timeout: 60)
        let out = r.output
        let dev = out.split(separator: "\n").first { $0.hasPrefix("origin=") }
            .map { String($0.dropFirst("origin=".count)) }
        if r.status == 0 {
            let notarized = out.contains("Notarized")
            return (.ok, (notarized ? "Vérifié et notarisé par Apple" : "Signé")
                    + (dev.map { " — \($0)" } ?? ""), origin)
        }
        if ext == "dmg" && out.contains("no usable signature") {
            // Beaucoup d'images disque ne sont pas signées : c'est l'app à l'intérieur qui compte
            return (.info, "Image disque non signée (l'app qu'elle contient sera vérifiée à l'ouverture)", origin)
        }
        return (.warning, "Refusé par Gatekeeper : éditeur non vérifié par Apple", origin)
    }

    private func push(_ e: GuardEvent) {
        events.insert(e, at: 0)
        if events.count > 100 { events.removeLast(events.count - 100) }
    }

    // MARK: Actions

    func markHandled(_ id: UUID) {
        if let i = events.firstIndex(where: { $0.id == id }) { events[i].handled = true }
    }

    func remove(_ e: GuardEvent) async {
        if let label = e.launchLabel {
            Shell.run("/bin/launchctl", ["bootout", "gui/\(getuid())/\(label)"], timeout: 10)
        }
        if FS.trash(e.url) {
            markHandled(e.id)
            return
        }
        // Éléments système (/Library/…) : mot de passe administrateur
        var cmd = ""
        if let l = e.launchLabel { cmd += "/bin/launchctl bootout system/\(Shell.quote(l)) 2>/dev/null; " }
        cmd += "/bin/mv \(Shell.quote(e.url.path)) \(Shell.quote(FS.home.appendingPathComponent(".Trash").path + "/"))"
        if await Shell.adminAsync(cmd).ok { markHandled(e.id) }
    }
}

// MARK: - Time Machine

enum TimeMachine {
    /// (sauvegarde configurée ?, date de la dernière sauvegarde)
    static func status() -> (configured: Bool, last: Date?) {
        let dest = Shell.run("/usr/bin/tmutil", ["destinationinfo"], timeout: 20).output
        let configured = dest.contains("Name") || dest.contains("ID")
        guard configured else { return (false, nil) }
        let latest = Shell.run("/usr/bin/tmutil", ["latestbackup"], timeout: 20).output
        // Les dossiers de sauvegarde sont nommés AAAA-MM-JJ-HHMMSS
        if let r = latest.range(of: #"\d{4}-\d{2}-\d{2}-\d{6}"#, options: .regularExpression) {
            let f = DateFormatter()
            f.dateFormat = "yyyy-MM-dd-HHmmss"
            return (true, f.date(from: String(latest[r])))
        }
        // Repli : préférences de Time Machine
        if let p = NSDictionary(contentsOfFile: "/Library/Preferences/com.apple.TimeMachine.plist"),
           let dests = p["Destinations"] as? [[String: Any]] {
            let dates = dests.compactMap { ($0["SnapshotDates"] as? [Date])?.max() }
            return (true, dates.max())
        }
        return (true, nil)
    }
}
