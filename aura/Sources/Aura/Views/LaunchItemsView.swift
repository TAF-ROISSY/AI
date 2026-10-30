import SwiftUI
import AppKit

struct LaunchItemsView: View {
    @EnvironmentObject var manager: AppManager
    @Etat private var toRemove: LaunchItem? = nil
    @Etat private var tab = 0

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .launch, subtitle: "Ce qui s'ouvre au démarrage et tourne en arrière-plan.")
            HStack {
                Picker("", selection: $tab) {
                    Text("Ouverture à la connexion (\(manager.loginItems.count))").tag(0)
                    Text("Agents en arrière-plan (\(manager.launchItems.count))").tag(1)
                }
                .pickerStyle(.segmented).frame(width: 460)
                if !manager.message.isEmpty { Text(manager.message).font(.callout).foregroundStyle(.green).lineLimit(2) }
                Spacer()
                Button("Réglages macOS…") { manager.openLoginItemsSettings() }
                Button { Task { await manager.load(); await manager.loadLoginItems() } } label: {
                    Label("Actualiser", systemImage: "arrow.clockwise")
                }
            }
            GlassCard(padding: 12) {
                if tab == 0 { loginList } else { agentList }
            }
        }
        .padding(28)
        .task {
            if manager.launchItems.isEmpty { await manager.load() }
            await manager.loadLoginItems()
        }
        .confirmationDialog("Supprimer \(toRemove?.label ?? "") ?", isPresented: Binding(
            get: { toRemove != nil }, set: { if !$0 { toRemove = nil } })) {
            Button("Arrêter et supprimer", role: .destructive) { if let i = toRemove { manager.removeLaunchItem(i) } }
        } message: {
            Text("Préfère « désactiver » si tu n'es pas sûr : c'est réversible. L'app concernée peut recréer l'agent.")
        }
    }

    private func appIcon(_ name: String) -> NSImage? {
        let candidates = [URL(fileURLWithPath: "/Applications/\(name).app"), FS.url("~/Applications/\(name).app")]
        guard let url = candidates.first(where: FS.exists) else { return nil }
        return NSWorkspace.shared.icon(forFile: url.path)
    }

    private var loginList: some View {
        Group {
            if manager.loginItems.isEmpty {
                EmptyState(icon: "power", title: "Aucune app au démarrage",
                           message: "Ou Aura n'a pas encore l'autorisation de lire la liste (Réglages › Confidentialité › Automatisation).")
            } else {
                ScrollView {
                    VStack(spacing: 0) {
                        ForEach(manager.loginItems, id: \.self) { name in
                            HStack(spacing: 12) {
                                if let img = appIcon(name) {
                                    Image(nsImage: img).resizable().frame(width: 30, height: 30)
                                } else {
                                    Image(systemName: "app.fill").font(.title2).frame(width: 30)
                                }
                                Text(name)
                                Spacer()
                                Button("Ne plus ouvrir") { Task { await manager.removeLoginItem(name) } }
                            }
                            .padding(.vertical, 8)
                            Divider().opacity(0.15)
                        }
                    }
                }
            }
        }
    }

    private var agentList: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(manager.launchItems) { item in
                    HStack(spacing: 12) {
                        Image(systemName: icon(item.scope)).foregroundStyle(color(item.scope)).frame(width: 24)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.label).lineLimit(1).foregroundStyle(item.disabled ? .secondary : .primary)
                            Text(item.program).font(.caption).foregroundStyle(.secondary)
                                .lineLimit(1).truncationMode(.middle)
                        }
                        Spacer()
                        if item.runAtLoad {
                            Text("au démarrage").font(.caption2).padding(.horizontal, 6).padding(.vertical, 2)
                                .background(.blue.opacity(0.2), in: Capsule())
                        }
                        Text(item.scope.rawValue).font(.caption).foregroundStyle(.secondary).frame(width: 140, alignment: .trailing)
                        if item.isRemovable {
                            Toggle("", isOn: Binding(get: { !item.disabled }, set: { manager.setLaunchItem(item, enabled: $0) }))
                                .toggleStyle(.switch).labelsHidden().controlSize(.small)
                                .help("Activer / désactiver sans supprimer")
                        }
                        Button { FS.reveal(item.url) } label: { Image(systemName: "magnifyingglass") }
                            .buttonStyle(.borderless)
                        Button { toRemove = item } label: { Image(systemName: "minus.circle.fill") }
                            .buttonStyle(.borderless).foregroundStyle(item.isRemovable ? .red : .secondary)
                            .disabled(!item.isRemovable)
                            .help(item.isRemovable ? "Arrêter et supprimer" : "Élément système : utilise le module Sécurité s'il est suspect")
                    }
                    .padding(.vertical, 8)
                    Divider().opacity(0.15)
                }
            }
        }
    }

    private func icon(_ s: LaunchItem.Scope) -> String {
        switch s {
        case .user: return "person.fill"
        case .global: return "person.3.fill"
        case .daemon: return "gearshape.2.fill"
        }
    }

    private func color(_ s: LaunchItem.Scope) -> Color {
        switch s {
        case .user: return .blue
        case .global: return .orange
        case .daemon: return .red
        }
    }
}
