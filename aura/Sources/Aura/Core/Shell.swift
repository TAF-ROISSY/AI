import Foundation
import AppKit
import Security

/// Exécution de commandes système (sans et avec droits administrateur).
enum Shell {
    @discardableResult
    static func run(_ path: String, _ args: [String] = [], timeout: TimeInterval = 120) -> (status: Int32, output: String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        do { try p.run() } catch { return (-1, error.localizedDescription) }
        var data = Data()
        let handle = pipe.fileHandleForReading
        let group = DispatchGroup()
        group.enter()
        DispatchQueue.global(qos: .utility).async {
            data = handle.readDataToEndOfFile()
            group.leave()
        }
        if group.wait(timeout: .now() + timeout) == .timedOut {
            p.terminate()
            group.wait()
        }
        p.waitUntilExit()
        return (p.terminationStatus, String(data: data, encoding: .utf8) ?? "")
    }

    /// Lance une commande avec le mot de passe administrateur (fenêtre macOS standard).
    /// Passe par l'outil `osascript` : la fenêtre de mot de passe et l'exécution se font
    /// dans un processus séparé, Aura ne se fige jamais. À appeler hors du fil principal.
    @discardableResult
    static func admin(_ command: String, timeout: TimeInterval = 3600) -> (ok: Bool, output: String) {
        let escaped = command.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
        let script = "do shell script \"\(escaped)\" with administrator privileges"
        let r = run("/usr/bin/osascript", ["-e", script], timeout: timeout)
        if r.status == 0 { return (true, r.output) }
        if r.output.contains("-128") { return (false, "Mot de passe non saisi (annulé)") }
        return (false, r.output.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    /// Version asynchrone, utilisable depuis l'interface.
    static func adminAsync(_ command: String, timeout: TimeInterval = 3600) async -> (ok: Bool, output: String) {
        await Task.detached(priority: .userInitiated) { Shell.admin(command, timeout: timeout) }.value
    }

    static func quote(_ s: String) -> String { "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'" }

    /// Requête SQLite via l'outil système (lecture des bases Safari, Chrome, TCC…).
    static func sqlite(_ db: URL, _ sql: String) -> [[String]] {
        let r = run("/usr/bin/sqlite3", ["-separator", "\u{1F}", "-readonly", db.path, sql], timeout: 30)
        guard r.status == 0 else { return [] }
        return r.output.split(separator: "\n").map { $0.components(separatedBy: "\u{1F}") }
    }
}

enum SignatureStatus: String {
    case apple = "Apple"
    case developer = "Développeur identifié"
    case adhoc = "Signature locale"
    case unsigned = "Non signé"
    case invalid = "Signature invalide"
    case unknown = "Inconnu"

    var isSuspicious: Bool { self == .unsigned || self == .invalid }
}

enum CodeSign {
    static func status(of url: URL) -> (SignatureStatus, team: String?) {
        var code: SecStaticCode?
        guard SecStaticCodeCreateWithPath(url as CFURL, [], &code) == errSecSuccess, let code else {
            return (.unknown, nil)
        }
        let check = SecStaticCodeCheckValidity(code, [], nil)
        if check == errSecCSUnsigned { return (.unsigned, nil) }
        guard check == errSecSuccess else { return (.invalid, nil) }
        var info: CFDictionary?
        SecCodeCopySigningInformation(code, SecCSFlags(rawValue: kSecCSSigningInformation), &info)
        let dict = info as? [String: Any] ?? [:]
        let team = dict[kSecCodeInfoTeamIdentifier as String] as? String
        let ident = dict[kSecCodeInfoIdentifier as String] as? String ?? ""
        if team == nil {
            // Les binaires Apple n'ont pas de Team ID mais sont signés par Apple
            if ident.hasPrefix("com.apple.") { return (.apple, nil) }
            return (.adhoc, nil)
        }
        return (.developer, team)
    }
}
