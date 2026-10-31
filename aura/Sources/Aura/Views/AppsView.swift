import SwiftUI
import AppKit

struct AppsView: View {
    @EnvironmentObject var manager: AppManager
    @Etat private var tab = 0
    @Etat private var search = ""
    @Etat private var filter = 0     // 0 toutes, 1 inutilisées 90 j, 2 lourdes > 1 Go
    @Etat private var selectedApp: AppInfo? = nil
    @Etat private var confirmUninstall = false
    @Etat private var lastMessage = ""

    private var filtered: [AppInfo] {
        var list = manager.apps
        if !search.isEmpty { list = list.filter { $0.name.localizedCaseInsensitiveContains(search) } }
        switch filter {
        case 1:
            let limit = Date().addingTimeInterval(-90 * 86400)
            list = list.filter { ($0.lastUsed ?? .distantPast) < limit }
        case 2: list = list.filter { $0.size > 1_000_000_000 }
        default: break
        }
        return list
    }

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .apps, subtitle: "Désinstalle ou réinitialise complètement, sans laisser de traces.")
            HStack {
                Picker("", selection: $tab) {
                    Text("Désinstalleur").tag(0)
                    Text("Restes orphelins").tag(1)
                }
                .pickerStyle(.segmented).frame(width: 300)
                Spacer()
                if !lastMessage.isEmpty { Text(lastMessage).font(.auraCallout).foregroundStyle(AuraTheme.green) }
            }
            if tab == 0 { uninstaller } else { orphansView }
        }
        .padding(28)
        .task { if manager.apps.isEmpty { await manager.load() } }
    }

    // MARK: Désinstalleur

    private var uninstaller: some View {
        HStack(alignment: .top, spacing: 14) {
            GlassCard(padding: 12) {
                VStack(spacing: 10) {
                    HStack {
                        TextField("Rechercher une app", text: $search).textFieldStyle(.roundedBorder)
                        Picker("", selection: $filter) {
                            Text("Toutes").tag(0)
                            Text("Inutilisées").tag(1)
                            Text("Lourdes").tag(2)
                        }
                        .frame(width: 130)
                    }
                    if manager.isLoading {
                        ProgressView("Inventaire des applications…").frame(maxHeight: .infinity)
                    } else {
                        ScrollView {
                            LazyVStack(spacing: 2) {
                                ForEach(filtered) { app in appRow(app) }
                            }
                        }
                    }
                    Text("\(filtered.count) apps · \(Fmt.bytes(filtered.reduce(0) { $0 + $1.size }))")
                        .font(.auraCaption).foregroundStyle(.secondary)
                }
            }
            .frame(width: 400)

            GlassCard {
                if let app = selectedApp { appDetail(app) }
                else {
                    EmptyState(icon: "square.grid.2x2", title: "Choisis une application",
                               message: "Aura retrouvera tous ses fichiers cachés : préférences, caches, conteneurs, agents…")
                }
            }
            .frame(maxHeight: .infinity, alignment: .top)
        }
        .confirmationDialog("Désinstaller \(selectedApp?.name ?? "") ?", isPresented: $confirmUninstall) {
            Button("Désinstaller", role: .destructive) {
                guard let app = selectedApp else { return }
                Task {
                    let r = await manager.uninstall(app)
                    lastMessage = r.ok ? "\(app.name) désinstallée — \(Fmt.bytes(r.freed)) envoyés à la Corbeille"
                                       : "Impossible de désinstaller \(app.name) (protégée par macOS ?)"
                    selectedApp = nil
                }
            }
        } message: {
            Text("L'application et les éléments cochés partent à la Corbeille.")
        }
    }

    private func appRow(_ app: AppInfo) -> some View {
        Button {
            selectedApp = app
            Task { await manager.searchLeftovers(for: app) }
        } label: {
            HStack(spacing: 10) {
                Image(nsImage: app.icon).resizable().frame(width: 32, height: 32)
                VStack(alignment: .leading, spacing: 1) {
                    Text(app.name).lineLimit(1)
                    Text("Utilisée \(Fmt.relativeDate(app.lastUsed))").font(.auraCaption2).foregroundStyle(.secondary)
                }
                Spacer()
                Text(Fmt.bytes(app.size)).font(.auraCaption.monospacedDigit()).foregroundStyle(.secondary)
            }
            .padding(8)
            .background(selectedApp?.id == app.id ? AuraTheme.amber.opacity(0.2) : .clear,
                        in: RoundedRectangle(cornerRadius: 10))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func appDetail(_ app: AppInfo) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 16) {
                Image(nsImage: app.icon).resizable().frame(width: 72, height: 72)
                VStack(alignment: .leading, spacing: 4) {
                    Text(app.name).font(.auraTitle2.bold())
                    Text([app.version.map { "Version \($0)" }, app.bundleID].compactMap { $0 }.joined(separator: " · "))
                        .font(.auraCaption).foregroundStyle(.secondary)
                    Text("Application : \(Fmt.bytes(app.size))").font(.auraCallout)
                }
                Spacer()
            }
            if app.isApple {
                Label("App système Apple : macOS empêche sa suppression.", systemImage: "exclamationmark.shield")
                    .foregroundStyle(AuraTheme.amber)
            }
            Text("Fichiers associés").fontWeight(.semibold)
            if manager.isSearchingLeftovers {
                ProgressView().frame(maxWidth: .infinity)
            } else if manager.leftovers.isEmpty {
                Text("Aucun fichier associé trouvé.").foregroundStyle(.secondary)
            } else {
                ScrollView {
                    VStack(spacing: 4) {
                        ForEach($manager.leftovers) { $l in
                            HStack(spacing: 10) {
                                Toggle("", isOn: $l.selected).labelsHidden().toggleStyle(.checkbox)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(l.url.lastPathComponent).lineLimit(1).truncationMode(.middle)
                                    Text(l.kind).font(.auraCaption2).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(Fmt.bytes(l.size)).font(.auraCaption).foregroundStyle(.secondary)
                                Button { FS.reveal(l.url) } label: { Image(systemName: "magnifyingglass") }
                                    .buttonStyle(.borderless)
                            }
                        }
                    }
                }
            }
            Spacer()
            HStack {
                let total = app.size + manager.leftovers.filter(\.selected).reduce(0) { $0 + $1.size }
                Text("Total : \(Fmt.bytes(total))").font(.auraTitle3.bold())
                Spacer()
                Button("Afficher dans le Finder") { FS.reveal(app.url) }
                Button("Réinitialiser") {
                    Task {
                        let f = await manager.reset(app)
                        lastMessage = "\(app.name) réinitialisée (\(Fmt.bytes(f)) de réglages et données à la Corbeille)"
                    }
                }
                .help("Supprime les fichiers associés cochés mais garde l'application : comme une première installation")
                .disabled(manager.leftovers.filter(\.selected).isEmpty)
                BigButton(title: "Désinstaller", icon: "trash", gradient: AuraTheme.danger) { confirmUninstall = true }
                    .disabled(app.isApple)
            }
        }
    }

    // MARK: Restes orphelins

    private var orphansView: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Fichiers laissés par des apps déjà supprimées").fontWeight(.semibold)
                    Spacer()
                    Button("Rechercher") { Task { await manager.findOrphans() } }
                    Button("Supprimer la sélection") {
                        Task {
                            let f = await manager.removeOrphans()
                            lastMessage = "\(Fmt.bytes(f)) envoyés à la Corbeille"
                        }
                    }
                    .buttonStyle(AuraButton(.primary))
                    .disabled(!manager.orphans.contains(where: \.selected))
                }
                Text("Vérifie chaque ligne : certains dossiers servent à des outils sans app visible.")
                    .font(.auraCaption).foregroundStyle(.secondary)
                if manager.isSearchingLeftovers {
                    ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if manager.orphans.isEmpty {
                    EmptyState(icon: "checkmark.seal", title: "Rien à signaler",
                               message: "Lance une recherche pour trouver les restes d'apps désinstallées.")
                } else {
                    ScrollView {
                        VStack(spacing: 4) {
                            ForEach($manager.orphans) { $o in
                                HStack(spacing: 10) {
                                    Toggle("", isOn: $o.selected).labelsHidden().toggleStyle(.checkbox)
                                    Text(o.url.lastPathComponent).lineLimit(1)
                                    Text(o.kind).font(.auraCaption2).foregroundStyle(.secondary)
                                    Spacer()
                                    Text(Fmt.bytes(o.size)).font(.auraCaption).foregroundStyle(.secondary)
                                    Button { FS.reveal(o.url) } label: { Image(systemName: "magnifyingglass") }
                                        .buttonStyle(.borderless)
                                }
                            }
                        }
                    }
                }
            }
        }
        .task { if manager.apps.isEmpty { await manager.load() } }
    }
}
