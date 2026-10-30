import Foundation
import AppKit

/// Une trace effaçable (historique, cookies, éléments récents…).
struct PrivacyItem: Identifiable {
    let id = UUID()
    let name: String
    let detail: String
    var count: Int?            // nombre d'entrées (si lisible)
    var size: Int64
    var selected: Bool
    let action: PrivacyAction
}

enum PrivacyAction {
    case deleteFiles([URL])
    case sql(URL, String)          // requête de nettoyage dans une base SQLite
    case command(String, [String])
    case adminCommand(String)
}

struct PrivacyGroup: Identifiable {
    let id: String
    let name: String
    let icon: String
    let bundleIDs: [String]        // pour vérifier que l'app est fermée
    var items: [PrivacyItem]
    var isRunning: Bool {
        bundleIDs.contains { !NSRunningApplication.runningApplications(withBundleIdentifier: $0).isEmpty }
    }
}

@MainActor
final class PrivacyManager: ObservableObject {
    @Published var groups: [PrivacyGroup] = []
    @Published var wifiNetworks: [String] = []
    @Published var isScanning = false
    @Published var message = ""

    func scan() async {
        isScanning = true
        groups = await Task.detached { Self.buildGroups() }.value
        wifiNetworks = await Task.detached { Self.readWifi() }.value
        isScanning = false
    }

    // MARK: Inventaire des traces

    nonisolated static func files(_ paths: [String]) -> [URL] {
        paths.map(FS.url).filter(FS.exists)
    }

    nonisolated static func item(_ name: String, _ detail: String, files urls: [URL], count: Int? = nil,
                                 selected: Bool = true) -> PrivacyItem? {
        guard !urls.isEmpty else { return nil }
        return PrivacyItem(name: name, detail: detail, count: count,
                           size: urls.reduce(0) { $0 + FS.size(of: $1) }, selected: selected,
                           action: .deleteFiles(urls))
    }

    nonisolated static func count(_ db: URL, _ table: String) -> Int? {
        guard FS.exists(db) else { return nil }
        return Shell.sqlite(db, "SELECT COUNT(*) FROM \(table);").first.flatMap { Int($0.first ?? "") }
    }

    nonisolated static func buildGroups() -> [PrivacyGroup] {
        var groups: [PrivacyGroup] = []

        // Safari
        let safariHistory = FS.url("~/Library/Safari/History.db")
        var safari: [PrivacyItem?] = []
        if FS.exists(safariHistory) {
            safari.append(PrivacyItem(name: "Historique de navigation", detail: "Pages visitées",
                                      count: count(safariHistory, "history_items"), size: FS.size(of: safariHistory),
                                      selected: true,
                                      action: .sql(safariHistory, "DELETE FROM history_visits; DELETE FROM history_items; VACUUM;")))
        }
        safari.append(item("Cookies", "Identifiants de connexion des sites (tu seras déconnecté)",
                           files: files(["~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies",
                                         "~/Library/Cookies/Cookies.binarycookies"]), selected: false))
        safari.append(item("Données des sites web", "Stockage local, bases IndexedDB, cache de service",
                           files: files(["~/Library/Safari/LocalStorage", "~/Library/Safari/Databases",
                                         "~/Library/Containers/com.apple.Safari/Data/Library/WebKit/WebsiteData"])))
        safari.append(item("Liste des téléchargements", "Historique des fichiers téléchargés (pas les fichiers)",
                           files: files(["~/Library/Safari/Downloads.plist"])))
        safari.append(item("Dernière session et onglets fermés", "Onglets restaurables",
                           files: files(["~/Library/Safari/LastSession.plist", "~/Library/Safari/RecentlyClosedTabs.plist"])))
        safari.append(item("Sites les plus visités", "Aperçus des Top Sites",
                           files: files(["~/Library/Safari/TopSites.plist", "~/Library/Containers/com.apple.Safari/Data/Library/Caches/com.apple.Safari/TabSnapshots"])))
        let s = safari.compactMap { $0 }
        if !s.isEmpty { groups.append(PrivacyGroup(id: "safari", name: "Safari", icon: "safari", bundleIDs: ["com.apple.Safari"], items: s)) }

        // Navigateurs Chromium
        let chromium: [(String, String, String)] = [
            ("Chrome", "~/Library/Application Support/Google/Chrome", "com.google.Chrome"),
            ("Edge", "~/Library/Application Support/Microsoft Edge", "com.microsoft.edgemac"),
            ("Brave", "~/Library/Application Support/BraveSoftware/Brave-Browser", "com.brave.Browser"),
            ("Vivaldi", "~/Library/Application Support/Vivaldi", "com.vivaldi.Vivaldi"),
            ("Arc", "~/Library/Application Support/Arc/User Data", "company.thebrowser.Browser")
        ]
        for (name, base, bid) in chromium {
            let profiles = FS.children(FS.url(base)).filter { $0.lastPathComponent == "Default" || $0.lastPathComponent.hasPrefix("Profile") }
            guard !profiles.isEmpty else { continue }
            func each(_ rel: [String]) -> [URL] {
                profiles.flatMap { p in rel.map { p.appendingPathComponent($0) } }.filter(FS.exists)
            }
            let historyDBs = each(["History"])
            let n = historyDBs.compactMap { count($0, "urls") }.reduce(0, +)
            let items: [PrivacyItem?] = [
                item("Historique de navigation", "Pages visitées et téléchargements",
                     files: each(["History", "History-journal", "Visited Links", "Top Sites", "Top Sites-journal", "Shortcuts", "Shortcuts-journal"]),
                     count: n > 0 ? n : nil),
                item("Cookies", "Tu seras déconnecté des sites", files: each(["Cookies", "Cookies-journal", "Network/Cookies", "Network/Cookies-journal"]),
                     selected: false),
                item("Sessions et onglets", "Onglets restaurables à la prochaine ouverture", files: each(["Sessions", "Current Session", "Last Session", "Current Tabs", "Last Tabs"])),
                item("Données des sites web", "Stockage local et bases des sites", files: each(["Local Storage", "IndexedDB", "Session Storage", "Service Worker", "databases"])),
                item("Saisie automatique", "Formulaires remplis (pas les mots de passe)", files: each(["Web Data", "Web Data-journal"]), selected: false)
            ]
            let list = items.compactMap { $0 }
            if !list.isEmpty { groups.append(PrivacyGroup(id: name, name: name, icon: "globe", bundleIDs: [bid], items: list)) }
        }

        // Firefox : on vide l'historique sans toucher aux favoris (même base)
        var ff: [PrivacyItem] = []
        for p in FS.children(FS.url("~/Library/Application Support/Firefox/Profiles")) {
            let places = p.appendingPathComponent("places.sqlite")
            if FS.exists(places) {
                ff.append(PrivacyItem(name: "Historique (\(p.lastPathComponent))", detail: "Les favoris sont conservés",
                                      count: count(places, "moz_historyvisits"), size: FS.size(of: places), selected: true,
                                      action: .sql(places, "DELETE FROM moz_historyvisits; DELETE FROM moz_inputhistory; VACUUM;")))
            }
            if let c = item("Cookies (\(p.lastPathComponent))", "Tu seras déconnecté des sites",
                            files: [p.appendingPathComponent("cookies.sqlite")].filter(FS.exists), selected: false) { ff.append(c) }
            if let f = item("Formulaires et session (\(p.lastPathComponent))", "Saisies et onglets restaurables",
                            files: ["formhistory.sqlite", "sessionstore.jsonlz4", "sessionstore-backups"].map { p.appendingPathComponent($0) }.filter(FS.exists)) {
                ff.append(f)
            }
        }
        if !ff.isEmpty { groups.append(PrivacyGroup(id: "firefox", name: "Firefox", icon: "flame", bundleIDs: ["org.mozilla.firefox"], items: ff)) }

        // Traces système
        var sys: [PrivacyItem?] = []
        let sfl = FS.url("~/Library/Application Support/com.apple.sharedfilelist")
        let recentDocs = FS.children(sfl).filter { $0.lastPathComponent.contains("RecentDocuments") || $0.lastPathComponent.contains("RecentApplications") || $0.lastPathComponent.contains("RecentServers") }
        let perApp = FS.children(sfl.appendingPathComponent("com.apple.LSSharedFileList.ApplicationRecentDocuments"))
        sys.append(item("Éléments récents", "Documents, apps et serveurs récents du menu Pomme et des apps",
                        files: recentDocs + perApp, count: recentDocs.count + perApp.count))
        sys.append(PrivacyItem(name: "Dossiers récents du Finder", detail: "Liste « Récents » du menu Aller",
                               count: nil, size: 0, selected: true,
                               action: .command("/usr/bin/defaults", ["delete", "com.apple.finder", "FXRecentFolders"])))
        sys.append(PrivacyItem(name: "Vignettes Coup d'œil", detail: "Aperçus mis en cache des fichiers consultés",
                               count: nil, size: 0, selected: true,
                               action: .command("/usr/bin/qlmanage", ["-r", "cache"])))
        sys.append(item("Historique du Terminal", "Commandes tapées (zsh, bash)",
                        files: files(["~/.zsh_history", "~/.bash_history", "~/.zsh_sessions", "~/.python_history", "~/.node_repl_history", "~/.lesshst"]),
                        selected: false))
        sys.append(item("Recherches Spotlight", "Recherches récentes et suggestions apprises",
                        files: files(["~/Library/Caches/com.apple.Spotlight", "~/Library/Application Support/com.apple.spotlight.Shortcuts",
                                      "~/Library/Application Support/com.apple.spotlight"])))
        let sl = sys.compactMap { $0 }
        if !sl.isEmpty { groups.append(PrivacyGroup(id: "system", name: "Traces macOS", icon: "apple.logo", bundleIDs: [], items: sl)) }

        // Messagerie et appels (on ne touche qu'aux caches, jamais aux conversations)
        let chat: [PrivacyItem?] = [
            item("Cache de Messages", "Aperçus de liens et caches (les conversations sont conservées)",
                 files: files(["~/Library/Caches/com.apple.Messages", "~/Library/Containers/com.apple.iChat/Data/Library/Caches"])),
            item("Cache de WhatsApp", "Fichiers temporaires", files: files(["~/Library/Containers/net.whatsapp.WhatsApp/Data/Library/Caches",
                                                                              "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/Library/Caches"])),
            item("Cache de Teams, Slack, Discord", "Fichiers temporaires",
                 files: files(["~/Library/Application Support/Microsoft/Teams/Cache", "~/Library/Containers/com.microsoft.teams2/Data/Library/Caches",
                               "~/Library/Application Support/Slack/Cache", "~/Library/Application Support/Slack/Service Worker/CacheStorage",
                               "~/Library/Application Support/discord/Cache"]))
        ]
        let cl = chat.compactMap { $0 }
        if !cl.isEmpty { groups.append(PrivacyGroup(id: "chat", name: "Messagerie", icon: "bubble.left.and.bubble.right", bundleIDs: [], items: cl)) }

        return groups
    }

    // MARK: Réseaux Wi-Fi mémorisés

    nonisolated static func wifiInterface() -> String {
        let out = Shell.run("/usr/sbin/networksetup", ["-listallhardwareports"], timeout: 10).output
        let lines = out.components(separatedBy: "\n")
        for (i, l) in lines.enumerated() where l.contains("Wi-Fi") || l.contains("AirPort") {
            if i + 1 < lines.count, let dev = lines[i + 1].components(separatedBy: "Device: ").last { return dev }
        }
        return "en0"
    }

    nonisolated static func readWifi() -> [String] {
        let out = Shell.run("/usr/sbin/networksetup", ["-listpreferredwirelessnetworks", wifiInterface()], timeout: 10).output
        return out.split(separator: "\n").dropFirst().map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }

    func forgetWifi(_ ssids: [String]) async {
        let iface = await Task.detached { Self.wifiInterface() }.value
        let cmd = ssids.map { "/usr/sbin/networksetup -removepreferredwirelessnetwork \(iface) \(Shell.quote($0))" }.joined(separator: "; ")
        let r = Shell.admin(cmd)
        message = r.ok ? "\(ssids.count) réseau(x) Wi-Fi oublié(s)" : "Opération annulée"
        wifiNetworks = await Task.detached { Self.readWifi() }.value
    }

    // MARK: Sélection et nettoyage

    func toggle(group: String, item: UUID) {
        guard let g = groups.firstIndex(where: { $0.id == group }),
              let i = groups[g].items.firstIndex(where: { $0.id == item }) else { return }
        groups[g].items[i].selected.toggle()
    }

    func quit(_ group: PrivacyGroup) {
        for bid in group.bundleIDs {
            NSRunningApplication.runningApplications(withBundleIdentifier: bid).forEach { $0.terminate() }
        }
    }

    func clean() async {
        let running = groups.filter { $0.isRunning && $0.items.contains(where: \.selected) }
        if !running.isEmpty {
            message = "Ferme d'abord : \(running.map(\.name).joined(separator: ", "))"
            return
        }
        let work = groups.flatMap { $0.items.filter(\.selected) }
        let done = await Task.detached { () -> Int in
            var n = 0
            for item in work {
                switch item.action {
                case .deleteFiles(let urls):
                    for u in urls { try? FS.fm.removeItem(at: u) }
                    n += 1
                case .sql(let db, let sql):
                    if Shell.run("/usr/bin/sqlite3", [db.path, sql], timeout: 60).status == 0 { n += 1 }
                case .command(let path, let args):
                    Shell.run(path, args, timeout: 30); n += 1
                case .adminCommand:
                    break
                }
            }
            return n
        }.value
        message = "\(done) types de traces effacés"
        await scan()
    }
}
