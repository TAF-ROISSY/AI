import SwiftUI
import AppKit

// MARK: - Sécurité

struct SecurityView: View {
    @EnvironmentObject var security: SecurityScanner
    @Etat private var confirm = false
    @Etat private var message = ""

    private var issues: Int { security.threats.filter { $0.level >= .medium }.count }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .security, subtitle: "Logiciels malveillants, publicitaires et réglages de sécurité.")

                GlassCard(padding: 24) {
                    HStack(spacing: 30) {
                        ZStack {
                            Circle().fill(statusColor.opacity(0.18)).frame(width: 130, height: 130)
                            Image(systemName: statusIcon).font(.system(size: 54, weight: .semibold)).foregroundStyle(statusColor)
                                .symbolEffect(.pulse, isActive: security.isScanning)
                        }
                        VStack(alignment: .leading, spacing: 10) {
                            Text(headline).font(.system(size: 26, weight: .bold, design: .rounded))
                            Text(security.isScanning ? security.progressLabel
                                 : security.lastScan.map { "Dernière analyse \(Fmt.relativeDate($0))" } ?? "Aucune analyse pour l'instant")
                                .foregroundStyle(.secondary)
                            HStack(spacing: 12) {
                                Picker("Profondeur", selection: $security.depth) {
                                    ForEach(ScanDepth.allCases) { Text($0.rawValue).tag($0) }
                                }
                                .pickerStyle(.segmented).frame(width: 290).labelsHidden()
                                BigButton(title: security.isScanning ? "Analyse…" : "Analyser", icon: "shield.lefthalf.filled",
                                          gradient: AuraTheme.good, busy: security.isScanning) {
                                    Task { await security.scan() }
                                }
                            }
                        }
                        Spacer()
                    }
                }

                if !security.checks.isEmpty { checksGrid }

                if !security.threats.isEmpty { threatsCard }

                if !message.isEmpty { Text(message).foregroundStyle(.green) }
            }
            .padding(28)
        }
        .task { if security.checks.isEmpty { await security.refreshChecks() } }
        .confirmationDialog("Supprimer les éléments cochés ?", isPresented: $confirm) {
            Button("Supprimer", role: .destructive) {
                Task {
                    let r = await security.removeSelected()
                    message = "\(r.removed) élément(s) neutralisé(s)" + (r.failed > 0 ? ", \(r.failed) en échec" : "")
                }
            }
        } message: {
            Text("Les lancements automatiques sont arrêtés et les fichiers envoyés à la Corbeille. Un mot de passe administrateur peut être demandé.")
        }
    }

    private var statusColor: Color {
        if security.isScanning { return .cyan }
        if issues > 0 { return .red }
        if security.checks.contains(where: { $0.ok == false }) { return .orange }
        return .green
    }
    private var statusIcon: String {
        if security.isScanning { return "shield.lefthalf.filled" }
        return issues > 0 ? "exclamationmark.shield.fill" : "checkmark.shield.fill"
    }
    private var headline: String {
        if security.isScanning { return "Analyse de sécurité…" }
        if security.lastScan == nil { return "Protège ton Mac" }
        return issues > 0 ? "\(issues) menace(s) à traiter" : "Aucune menace détectée"
    }

    private var checksGrid: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 300), spacing: 12)], spacing: 12) {
            ForEach(security.checks) { c in
                GlassCard(padding: 14) {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: c.ok == true ? "checkmark.circle.fill" : c.ok == false ? "xmark.octagon.fill" : "questionmark.circle")
                            .font(.title2).foregroundStyle(c.ok == true ? .green : c.ok == false ? .red : .secondary)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(c.title).fontWeight(.semibold)
                            Text(c.detail).font(.caption).foregroundStyle(.secondary)
                            if c.ok == false {
                                Text(c.fixHint).font(.caption).foregroundStyle(.orange)
                                if let s = c.settingsURL, let u = URL(string: s) {
                                    Button("Corriger…") { NSWorkspace.shared.open(u) }.controlSize(.small)
                                }
                            }
                        }
                        Spacer()
                    }
                }
            }
        }
    }

    private var threatsCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Éléments détectés").fontWeight(.semibold)
                    Spacer()
                    Button("Supprimer la sélection") { confirm = true }
                        .buttonStyle(.borderedProminent).tint(.red)
                        .disabled(!security.threats.contains { $0.selected && $0.removable })
                }
                ForEach(security.threats) { t in
                    HStack(alignment: .top, spacing: 10) {
                        if t.removable {
                            Button { security.toggle(t.id) } label: { CheckCircle(on: t.selected, tint: .red) }.buttonStyle(.plain)
                        } else {
                            Image(systemName: "info.circle").foregroundStyle(.secondary).font(.title3)
                        }
                        VStack(alignment: .leading, spacing: 3) {
                            HStack(spacing: 6) {
                                Text(t.title).fontWeight(.medium).lineLimit(1)
                                Text(t.level.label).font(.caption2.bold())
                                    .padding(.horizontal, 6).padding(.vertical, 1)
                                    .background(Color(nsColor: t.level.color).opacity(0.3), in: Capsule())
                                Text(t.kind.rawValue).font(.caption2).foregroundStyle(.secondary)
                            }
                            Text(t.detail).font(.caption).foregroundStyle(.secondary).lineLimit(3)
                        }
                        Spacer()
                        if t.url.path != "/" {
                            Button { FS.reveal(t.url) } label: { Image(systemName: "magnifyingglass") }.buttonStyle(.borderless)
                        }
                        Button("Ignorer") { security.ignore(t) }.buttonStyle(.borderless).font(.caption)
                    }
                    Divider().opacity(0.15)
                }
            }
        }
    }
}

// MARK: - Confidentialité

struct PrivacyView: View {
    @EnvironmentObject var privacy: PrivacyManager
    @Etat private var confirm = false
    @Etat private var wifiSelection: Set<String> = []

    private var selectedCount: Int { privacy.groups.reduce(0) { $0 + $1.items.filter(\.selected).count } }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .privacy, subtitle: "Efface les traces de navigation et d'activité, sans toucher à tes fichiers.")
                HStack {
                    if !privacy.message.isEmpty { Text(privacy.message).foregroundStyle(.green) }
                    Spacer()
                    Button { Task { await privacy.scan() } } label: { Label("Analyser", systemImage: "arrow.clockwise") }
                    BigButton(title: "Effacer \(selectedCount) éléments", icon: "hand.raised.fill", gradient: AuraTheme.good) {
                        confirm = true
                    }
                    .disabled(selectedCount == 0)
                }

                if privacy.isScanning {
                    ProgressView("Recherche des traces…").padding(40)
                } else if privacy.groups.isEmpty {
                    GlassCard { EmptyState(icon: "hand.raised", title: "Rien d'analysé", message: "Lance une analyse pour voir les traces laissées par tes navigateurs et macOS.") }
                } else {
                    ForEach(privacy.groups) { g in groupCard(g) }
                    wifiCard
                }
            }
            .padding(28)
        }
        .task { if privacy.groups.isEmpty { await privacy.scan() } }
        .confirmationDialog("Effacer définitivement \(selectedCount) types de traces ?", isPresented: $confirm) {
            Button("Effacer", role: .destructive) { Task { await privacy.clean() } }
        } message: {
            Text("Les navigateurs concernés doivent être fermés. Mots de passe et favoris ne sont jamais touchés.")
        }
    }

    private func groupCard(_ g: PrivacyGroup) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: g.icon).font(.title3).foregroundStyle(.mint).frame(width: 26)
                    Text(g.name).font(.headline)
                    if g.isRunning {
                        Text("ouvert").font(.caption2).padding(.horizontal, 6).padding(.vertical, 1)
                            .background(.orange.opacity(0.3), in: Capsule())
                        Button("Quitter") { privacy.quit(g) }.controlSize(.small)
                    }
                    Spacer()
                }
                ForEach(g.items) { item in
                    Button { privacy.toggle(group: g.id, item: item.id) } label: {
                        HStack(spacing: 10) {
                            CheckCircle(on: item.selected, tint: .mint)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(item.name)
                                Text(item.detail).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if let c = item.count { Text("\(c) entrées").font(.caption).foregroundStyle(.secondary) }
                            if item.size > 0 { Text(Fmt.bytes(item.size)).font(.caption.monospacedDigit()).foregroundStyle(.secondary) }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var wifiCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "wifi").font(.title3).foregroundStyle(.mint).frame(width: 26)
                    Text("Réseaux Wi-Fi mémorisés (\(privacy.wifiNetworks.count))").font(.headline)
                    Spacer()
                    Button("Oublier \(wifiSelection.count) réseau(x)") {
                        Task { await privacy.forgetWifi(Array(wifiSelection)); wifiSelection = [] }
                    }
                    .disabled(wifiSelection.isEmpty)
                }
                Text("Ton Mac se reconnecte automatiquement à ces réseaux, y compris des Wi-Fi publics oubliés depuis longtemps.")
                    .font(.caption).foregroundStyle(.secondary)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 220))], alignment: .leading, spacing: 6) {
                    ForEach(privacy.wifiNetworks, id: \.self) { ssid in
                        Button {
                            if wifiSelection.contains(ssid) { wifiSelection.remove(ssid) } else { wifiSelection.insert(ssid) }
                        } label: {
                            HStack { CheckCircle(on: wifiSelection.contains(ssid), tint: .mint); Text(ssid).lineLimit(1) }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }
}

// MARK: - Autorisations des apps

struct PermissionsView: View {
    @EnvironmentObject var perms: PermissionsManager
    @Etat private var service: PermissionService = .camera

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .permissions, subtitle: "Quelles apps peuvent voir ton écran, t'écouter ou lire tes fichiers.")
            if !perms.readable && !perms.isLoading {
                Label("Accorde l'Accès complet au disque à Aura pour lire les autorisations.", systemImage: "lock.fill")
                    .foregroundStyle(.orange)
            }
            HStack(alignment: .top, spacing: 14) {
                GlassCard(padding: 8) {
                    ScrollView {
                        VStack(spacing: 2) {
                            ForEach(PermissionService.allCases) { s in
                                let n = perms.apps(for: s).count
                                Button { service = s } label: {
                                    HStack(spacing: 10) {
                                        Image(systemName: s.icon).frame(width: 22).foregroundStyle(s.isSensitive ? .orange : .indigo)
                                        Text(s.title).lineLimit(1)
                                        Spacer()
                                        if n > 0 { Text("\(n)").font(.caption.bold()).foregroundStyle(.secondary) }
                                    }
                                    .padding(8)
                                    .background(service == s ? Color.indigo.opacity(0.3) : .clear, in: RoundedRectangle(cornerRadius: 8))
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                .frame(width: 290)

                GlassCard {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Image(systemName: service.icon).font(.title2).foregroundStyle(.indigo)
                            Text(service.title).font(.title3.bold())
                            Spacer()
                            Button("Ouvrir dans Réglages") { perms.openSettings(service) }
                        }
                        if !perms.message.isEmpty { Text(perms.message).font(.caption).foregroundStyle(.green) }
                        let list = perms.apps(for: service)
                        if perms.isLoading {
                            ProgressView().frame(maxWidth: .infinity)
                        } else if list.isEmpty {
                            EmptyState(icon: "checkmark.shield", title: "Aucune app", message: "Aucune application n'a demandé cette autorisation.")
                        } else {
                            ScrollView {
                                VStack(spacing: 6) {
                                    ForEach(list) { p in
                                        HStack(spacing: 10) {
                                            if let u = p.appURL {
                                                Image(nsImage: NSWorkspace.shared.icon(forFile: u.path)).resizable().frame(width: 28, height: 28)
                                            } else {
                                                Image(systemName: "app.dashed").frame(width: 28)
                                            }
                                            VStack(alignment: .leading, spacing: 1) {
                                                Text(p.appName)
                                                Text(p.client).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                                            }
                                            Spacer()
                                            Text(p.allowed ? "Autorisée" : "Refusée").font(.caption)
                                                .foregroundStyle(p.allowed ? .orange : .secondary)
                                            Button("Retirer") { Task { await perms.revoke(p) } }.controlSize(.small)
                                        }
                                        Divider().opacity(0.15)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        .padding(28)
        .task { if perms.permissions.isEmpty { await perms.load() } }
    }
}
