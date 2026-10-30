import Foundation
import AppKit
import SwiftUI

/// Mise à jour d'Aura elle-même, depuis les « releases » GitHub du dépôt TAF-ROISSY/AI.
/// Les versions d'Aura y sont marquées « aura-vX.Y.Z » (le dépôt héberge aussi d'autres applis)
/// et contiennent Aura.zip, compilée automatiquement par GitHub Actions.
@MainActor
final class SelfUpdater: ObservableObject {
    static let repo = "TAF-ROISSY/AI"
    static let tagPrefix = "aura-v"

    struct Release: Equatable {
        let version: String
        let notes: String
        let assetURL: URL
        let page: URL?
        let date: Date?
    }

    @Published var available: Release?
    @Published var isChecking = false
    @Published var isInstalling = false
    @Published var progress: Double = 0
    @Published var status = ""
    @Published var lastResult = ""

    @Pref("aura.update.auto") var autoInstall = false
    @Pref("aura.update.lastCheck") var lastCheck: Double = 0

    private var timer: Timer?

    var currentVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0"
    }

    /// Vérifie au démarrage (après 15 s) puis toutes les 6 heures.
    func start() {
        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: 6 * 3600, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.check(silent: true) }
        }
        Task {
            try? await Task.sleep(nanoseconds: 15_000_000_000)
            await check(silent: true)
        }
    }

    // MARK: Vérification

    func check(silent: Bool) async {
        guard !isChecking, !isInstalling else { return }
        isChecking = true
        defer { isChecking = false }
        lastCheck = Date().timeIntervalSince1970

        guard let url = URL(string: "https://api.github.com/repos/\(Self.repo)/releases?per_page=40") else { return }
        var req = URLRequest(url: url, timeoutInterval: 20)
        req.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        req.setValue("Aura/\(currentVersion)", forHTTPHeaderField: "User-Agent")

        guard let resp = try? await URLSession.shared.data(for: req),
              let http = resp.1 as? HTTPURLResponse, http.statusCode == 200,
              let list = try? JSONSerialization.jsonObject(with: resp.0) as? [[String: Any]] else {
            if !silent { lastResult = "Impossible de joindre le serveur de mises à jour." }
            return
        }
        // Dernière version publiée d'Aura (on ignore les brouillons et les autres applis du dépôt)
        let releases = list.filter {
            ($0["tag_name"] as? String)?.hasPrefix(Self.tagPrefix) == true
                && ($0["draft"] as? Bool) != true && ($0["prerelease"] as? Bool) != true
        }
        guard let j = releases.max(by: {
            versionIsNewer(String(($1["tag_name"] as? String ?? "").dropFirst(Self.tagPrefix.count)),
                           than: String(($0["tag_name"] as? String ?? "").dropFirst(Self.tagPrefix.count)))
        }), let tag = j["tag_name"] as? String else {
            if !silent { lastResult = "Aucune version publiée pour l'instant." }
            return
        }
        let version = String(tag.dropFirst(Self.tagPrefix.count))
        let assets = j["assets"] as? [[String: Any]] ?? []
        guard let asset = assets.first(where: { ($0["name"] as? String)?.hasSuffix(".zip") == true }),
              let dl = (asset["browser_download_url"] as? String).flatMap(URL.init(string:)) else {
            if !silent { lastResult = "La dernière version est encore en préparation." }
            return
        }

        if versionIsNewer(version, than: currentVersion) {
            let iso = ISO8601DateFormatter()
            available = Release(version: version,
                                notes: (j["body"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines),
                                assetURL: dl,
                                page: (j["html_url"] as? String).flatMap(URL.init(string:)),
                                date: (j["published_at"] as? String).flatMap { iso.date(from: $0) })
            lastResult = "Aura \(version) est disponible."
            if silent && autoInstall { await install() }
        } else {
            available = nil
            lastResult = "Aura est à jour (version \(currentVersion))."
        }
    }

    // MARK: Installation

    func install() async {
        guard let rel = available, !isInstalling else { return }
        isInstalling = true
        status = "Téléchargement d'Aura \(rel.version)…"
        progress = 0.1

        let work = FS.fm.temporaryDirectory.appendingPathComponent("aura-update-\(UUID().uuidString)")
        do {
            try FS.fm.createDirectory(at: work, withIntermediateDirectories: true)
            let (tmp, _) = try await URLSession.shared.download(from: rel.assetURL)
            let zip = work.appendingPathComponent("Aura.zip")
            try FS.fm.moveItem(at: tmp, to: zip)
            progress = 0.6
            status = "Décompression…"

            let unzip = await Task.detached { Shell.run("/usr/bin/ditto", ["-x", "-k", zip.path, work.path], timeout: 120) }.value
            guard unzip.status == 0,
                  let newApp = FS.children(work).first(where: { $0.pathExtension == "app" }) else {
                fail("Archive de mise à jour invalide.")
                return
            }
            progress = 0.85
            status = "Installation et redémarrage…"

            // L'app ne peut pas se remplacer pendant qu'elle tourne : un petit script
            // attend qu'Aura se ferme, remplace l'app puis la relance.
            let target = Bundle.main.bundleURL.pathExtension == "app"
                ? Bundle.main.bundleURL : URL(fileURLWithPath: "/Applications/Aura.app")
            let script = work.appendingPathComponent("install.sh")
            let pid = ProcessInfo.processInfo.processIdentifier
            let body = """
            #!/bin/bash
            while kill -0 \(pid) 2>/dev/null; do sleep 0.5; done
            T=\(Shell.quote(target.path))
            N=\(Shell.quote(newApp.path))
            if ! { rm -rf "$T" && /usr/bin/ditto "$N" "$T"; } 2>/dev/null; then
              /usr/bin/osascript -e "do shell script \\"rm -rf '$T' && /usr/bin/ditto '$N' '$T'\\" with administrator privileges"
            fi
            /usr/bin/xattr -dr com.apple.quarantine "$T" 2>/dev/null
            /usr/bin/open "$T"
            """
            try body.write(to: script, atomically: true, encoding: .utf8)
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/bin/bash")
            p.arguments = [script.path]
            try p.run()
            progress = 1
            NSApp.terminate(nil)
        } catch {
            fail("Téléchargement interrompu : \(error.localizedDescription)")
        }
    }

    private func fail(_ msg: String) {
        status = msg
        lastResult = msg
        isInstalling = false
        progress = 0
    }
}
