import SwiftUI
import AppKit

// MARK: - Maintenance

struct MaintenanceView: View {
    @EnvironmentObject var maint: MaintenanceManager

    private var selectedCount: Int { maint.tasks.filter(\.selected).count }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .maintenance, subtitle: "Les petits réglages qui gardent ton Mac rapide et stable.")
                HStack {
                    if maint.recommendedCount > 0 {
                        Label("\(maint.recommendedCount) tâche(s) recommandée(s)", systemImage: "star.fill").foregroundStyle(.orange)
                    }
                    Spacer()
                    Button("Sélectionner les recommandées") { maint.selectRecommended() }
                    BigButton(title: maint.running != nil ? "En cours…" : "Lancer \(selectedCount) tâche(s)",
                              icon: "wrench.and.screwdriver.fill", busy: maint.running != nil) {
                        Task { await maint.runSelected() }
                    }
                    .disabled(selectedCount == 0)
                }
                if let r = maint.running {
                    HStack { ProgressView().controlSize(.small); Text(r).foregroundStyle(.secondary).lineLimit(1) }
                }
                if !maint.log.isEmpty {
                    GlassCard(padding: 14) {
                        VStack(alignment: .leading, spacing: 4) { ForEach(maint.log, id: \.self) { Text($0).font(.callout) } }
                    }
                }
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 340), spacing: 12)], spacing: 12) {
                    ForEach(maint.tasks) { t in
                        Button { maint.toggle(t.id) } label: {
                            GlassCard(padding: 14) {
                                HStack(alignment: .top, spacing: 12) {
                                    CheckCircle(on: t.selected, tint: .orange)
                                    Image(systemName: t.icon).font(.title2).foregroundStyle(.orange).frame(width: 30)
                                    VStack(alignment: .leading, spacing: 3) {
                                        HStack(spacing: 6) {
                                            Text(t.name).fontWeight(.semibold)
                                            if maint.isRecommended(t) {
                                                Text("recommandée").font(.caption2).padding(.horizontal, 5).padding(.vertical, 1)
                                                    .background(.orange.opacity(0.3), in: Capsule())
                                            }
                                            if t.needsAdmin { Image(systemName: "lock.fill").font(.caption2).foregroundStyle(.secondary) }
                                        }
                                        Text(t.detail).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                                        Text(maint.lastRun(t).map { "Dernière fois \(Fmt.relativeDate($0))" } ?? "Jamais lancée")
                                            .font(.caption2).foregroundStyle(.tertiary)
                                    }
                                    Spacer()
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                if !maint.snapshots.isEmpty {
                    GlassCard {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(maint.snapshots.count) instantané(s) Time Machine locaux").fontWeight(.semibold)
                            ForEach(maint.snapshots, id: \.self) { Text($0).font(.caption.monospaced()).foregroundStyle(.secondary) }
                        }
                    }
                }
            }
            .padding(28)
        }
        .task { await maint.loadSnapshots() }
    }
}

// MARK: - Mises à jour

struct UpdaterView: View {
    @EnvironmentObject var updater: UpdateManager

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .updater, subtitle: "Toutes tes apps à jour : éditeurs, App Store et Homebrew.")
            HStack {
                if updater.isChecking {
                    ProgressView(value: Double(updater.checked), total: Double(max(1, updater.total))).frame(width: 220)
                    Text("\(updater.checked)/\(updater.total) apps vérifiées").font(.caption).foregroundStyle(.secondary)
                } else if let d = updater.lastCheck {
                    Text("Vérifié \(Fmt.relativeDate(d))").foregroundStyle(.secondary)
                }
                if !updater.message.isEmpty { Text(updater.message).foregroundStyle(.green).lineLimit(2) }
                Spacer()
                Button { Task { await updater.check() } } label: { Label("Vérifier", systemImage: "arrow.clockwise") }
                    .disabled(updater.isChecking)
                BigButton(title: "Mettre à jour (\(updater.updates.filter(\.selected).count))", icon: "arrow.down.circle.fill") {
                    Task { await updater.updateSelected() }
                }
                .disabled(!updater.updates.contains(where: \.selected))
            }

            if !updater.macOSUpdates.isEmpty {
                GlassCard(padding: 14) {
                    HStack {
                        Image(systemName: "apple.logo").font(.title2)
                        VStack(alignment: .leading) {
                            Text("Mises à jour macOS disponibles").fontWeight(.semibold)
                            ForEach(updater.macOSUpdates, id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
                        }
                        Spacer()
                        Button("Ouvrir Mise à jour de logiciels") { updater.openMacOSUpdates() }
                    }
                }
            }

            GlassCard(padding: 10) {
                if updater.updates.isEmpty {
                    EmptyState(icon: updater.isChecking ? "hourglass" : "checkmark.seal.fill",
                               title: updater.isChecking ? "Vérification en cours…" : (updater.lastCheck == nil ? "Lance une vérification" : "Tout est à jour"),
                               message: "Aura interroge les flux des éditeurs (Sparkle), l'App Store et Homebrew.")
                } else {
                    ScrollView {
                        VStack(spacing: 0) {
                            ForEach(updater.updates) { u in
                                HStack(spacing: 12) {
                                    Button { updater.toggle(u.id) } label: { CheckCircle(on: u.selected, tint: .cyan) }.buttonStyle(.plain)
                                    if let a = u.appURL {
                                        Image(nsImage: NSWorkspace.shared.icon(forFile: a.path)).resizable().frame(width: 34, height: 34)
                                    } else {
                                        Image(systemName: "terminal.fill").font(.title2).frame(width: 34).foregroundStyle(.secondary)
                                    }
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(u.name).fontWeight(.medium)
                                        HStack(spacing: 6) {
                                            Text(u.installed).foregroundStyle(.secondary)
                                            Image(systemName: "arrow.right").font(.caption2)
                                            Text(u.available).foregroundStyle(.cyan).fontWeight(.semibold)
                                            Text("· \(u.source.rawValue)").foregroundStyle(.secondary)
                                        }
                                        .font(.caption)
                                    }
                                    Spacer()
                                    if let n = u.notesURL {
                                        Button("Nouveautés") { NSWorkspace.shared.open(n) }.buttonStyle(.borderless)
                                    }
                                    if updater.busy.contains(u.id) {
                                        ProgressView().controlSize(.small)
                                    } else {
                                        Button("Mettre à jour") { Task { await updater.update(u) } }
                                    }
                                }
                                .padding(10)
                                Divider().opacity(0.15)
                            }
                        }
                    }
                }
            }
        }
        .padding(28)
        .task { if updater.lastCheck == nil && !updater.isChecking { await updater.check() } }
    }
}

// MARK: - Extensions

struct ExtensionsView: View {
    @EnvironmentObject var ext: ExtensionManager
    @Etat private var category: ExtensionCategory = .browser
    @Etat private var toRemove: SystemExtensionItem? = nil

    private func count(_ c: ExtensionCategory) -> Int {
        c == .browser ? ext.browserExtensions.count : ext.items.filter { $0.category == c }.count
    }

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .extensions, subtitle: "Modules ajoutés aux navigateurs, au Finder et à macOS.")
            HStack {
                if !ext.message.isEmpty { Text(ext.message).foregroundStyle(.green) }
                Spacer()
                Button { Task { await ext.load() } } label: { Label("Actualiser", systemImage: "arrow.clockwise") }
            }
            HStack(alignment: .top, spacing: 14) {
                GlassCard(padding: 8) {
                    VStack(spacing: 2) {
                        ForEach(ExtensionCategory.allCases) { c in
                            Button { category = c } label: {
                                HStack(spacing: 10) {
                                    Image(systemName: c.icon).frame(width: 22).foregroundStyle(.purple)
                                    Text(c.rawValue).lineLimit(1)
                                    Spacer()
                                    Text("\(count(c))").font(.caption.bold()).foregroundStyle(.secondary)
                                }
                                .padding(8)
                                .background(category == c ? Color.purple.opacity(0.3) : .clear, in: RoundedRectangle(cornerRadius: 8))
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                        }
                        Spacer()
                    }
                }
                .frame(width: 290)

                GlassCard(padding: 10) {
                    if ext.isLoading {
                        ProgressView("Inventaire des extensions…").frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if category == .browser {
                        browserList
                    } else {
                        systemList
                    }
                }
            }
        }
        .padding(28)
        .task { if ext.items.isEmpty && ext.browserExtensions.isEmpty { await ext.load() } }
        .confirmationDialog("Supprimer \(toRemove?.name ?? "") ?", isPresented: Binding(
            get: { toRemove != nil }, set: { if !$0 { toRemove = nil } })) {
            Button("Envoyer à la Corbeille", role: .destructive) { if let t = toRemove { ext.remove(t) } }
        }
    }

    private var browserList: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(Set(ext.browserExtensions.map(\.browser))).sorted(), id: \.self) { b in
                    HStack {
                        Text(b).font(.headline)
                        Spacer()
                        Button("Gérer dans \(b)") { ext.openBrowserExtensionsPage(b) }.buttonStyle(.borderless)
                    }
                    .padding(.top, 10).padding(.horizontal, 8)
                    ForEach(ext.browserExtensions.filter { $0.browser == b }) { e in
                        HStack(spacing: 10) {
                            Image(systemName: "puzzlepiece.extension.fill").foregroundStyle(.purple)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(e.name).lineLimit(1)
                                Text("v\(e.version) · \(e.identifier)").font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                            }
                            Spacer()
                            if e.permissions.contains("<all_urls>") {
                                Text("accès à tous les sites").font(.caption2).padding(.horizontal, 5).padding(.vertical, 1)
                                    .background(.orange.opacity(0.25), in: Capsule())
                            }
                            Button { FS.reveal(e.url) } label: { Image(systemName: "magnifyingglass") }.buttonStyle(.borderless)
                            Button("Retirer") { ext.remove(e) }.controlSize(.small)
                        }
                        .padding(8)
                    }
                }
            }
        }
    }

    private var systemList: some View {
        let list = ext.items.filter { $0.category == category }
        return Group {
            if list.isEmpty {
                EmptyState(icon: category.icon, title: "Rien ici", message: "Aucun élément de ce type n'est installé.")
            } else {
                ScrollView {
                    VStack(spacing: 0) {
                        ForEach(list) { item in
                            HStack(spacing: 10) {
                                Image(systemName: category.icon).foregroundStyle(.purple).frame(width: 22)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(item.name).lineLimit(1)
                                    Text(item.detail).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                                }
                                Spacer()
                                if item.pluginID != nil {
                                    Toggle("", isOn: Binding(get: { item.enabled }, set: { ext.setEnabled(item, $0) }))
                                        .toggleStyle(.switch).labelsHidden().controlSize(.small)
                                } else {
                                    Button("Supprimer") { toRemove = item }.controlSize(.small)
                                }
                                Button { FS.reveal(item.url) } label: { Image(systemName: "magnifyingglass") }.buttonStyle(.borderless)
                            }
                            .padding(8)
                            Divider().opacity(0.12)
                        }
                    }
                }
            }
        }
    }
}
