import SwiftUI
import AppKit

struct DuplicatesView: View {
    @EnvironmentObject var tools: FileTools
    @EnvironmentObject var router: Router
    @EnvironmentObject var volumes: VolumeManager
    @Etat private var roots: [URL] = [FS.home]
    @Etat private var minSizeKB: Int = 100
    @Etat private var kindFilter = "Tous"
    @Etat private var confirm = false
    @Etat private var permanent = false
    @Etat private var message = ""

    private let kinds = ["Tous", "Image", "Vidéo", "Audio", "Document", "Archive", "Autre"]

    private var visibleGroups: [DuplicateGroup] {
        kindFilter == "Tous" ? tools.duplicates : tools.duplicates.filter { $0.files.first?.kind == kindFilter }
    }

    private var selectedSize: Int64 {
        tools.duplicates.reduce(Int64(0)) { acc, g in
            let sel = g.files.filter(\.selected)
            return sel.count < g.files.count ? acc + sel.reduce(Int64(0)) { $0 + $1.size } : acc
        }
    }
    private var selectedCount: Int {
        tools.duplicates.reduce(0) { acc, g in
            let n = g.files.filter(\.selected).count
            return n < g.files.count ? acc + n : acc
        }
    }
    /// Une copie cochée est-elle sur un support externe ? (la Corbeille n'y libère rien)
    private var touchesExternal: Bool {
        tools.duplicates.contains { g in g.files.contains { $0.selected && !isOnMac($0.url) } }
    }

    var body: some View {
        VStack(spacing: 16) {
            ModuleHeader(module: .duplicates, subtitle: "Comparaison au contenu près (SHA-256), sur le Mac et sur tes supports.")

            sourcesCard
            rulesBar

            if tools.duplicates.isEmpty {
                GlassCard {
                    EmptyState(icon: "square.on.square",
                               title: tools.isBusy ? tools.status : "Pas encore de doublons",
                               message: "Ajoute un ou plusieurs dossiers ou supports (ex. ton dossier Photos + une clé USB) pour trouver les copies entre eux.")
                }
            } else {
                summary
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(visibleGroups) { g in groupCard(g) }
                    }
                }
            }
        }
        .padding(28)
        .onAppear {
            let requested = router.consumeRoots()
            if !requested.isEmpty { roots = requested }
        }
        .confirmationDialog(permanent ? "Supprimer définitivement \(selectedCount) copies ?"
                                      : "Envoyer \(selectedCount) copies à la Corbeille ?", isPresented: $confirm) {
            Button(permanent ? "Supprimer définitivement" : "Envoyer à la Corbeille", role: .destructive) {
                Task {
                    let freed = await tools.removeSelectedDuplicates(permanent: permanent)
                    message = "\(Fmt.bytes(freed)) libérés"
                    volumes.refresh()
                }
            }
        } message: {
            Text("Au moins une copie de chaque fichier est toujours conservée.")
        }
    }

    // MARK: Sources

    private var sourcesCard: some View {
        GlassCard(padding: 14) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Emplacements analysés").fontWeight(.semibold)
                    Spacer()
                    Menu {
                        Button("Choisir un dossier…") { if let u = pickFolder() { add(u) } }
                        if !volumes.externalVolumes.isEmpty {
                            Divider()
                            ForEach(volumes.externalVolumes) { v in
                                Button { add(v.url) } label: { Label(v.name, systemImage: v.symbol) }
                            }
                        }
                        Divider()
                        Button("Mon dossier personnel") { add(FS.home) }
                        Button("Images") { add(FS.url("~/Pictures")) }
                        Button("Documents") { add(FS.url("~/Documents")) }
                        Button("Téléchargements") { add(FS.url("~/Downloads")) }
                    } label: { Label("Ajouter", systemImage: "plus") }
                    .fixedSize()
                    Picker("Taille min.", selection: $minSizeKB) {
                        Text("1 Ko").tag(1)
                        Text("100 Ko").tag(100)
                        Text("1 Mo").tag(1000)
                        Text("10 Mo").tag(10_000)
                    }
                    .frame(width: 170)
                    BigButton(title: tools.isBusy ? "\(tools.scannedCount) fichiers…" : "Chercher",
                              icon: "square.on.square", busy: tools.isBusy) {
                        message = ""
                        Task { await tools.findDuplicates(in: roots, minSize: Int64(minSizeKB) * 1000) }
                    }
                    .disabled(roots.isEmpty)
                }
                FlowChips(items: roots.map { RootChip(url: $0, label: label(for: $0)) }) { url in
                    roots.removeAll { $0 == url }
                }
            }
        }
    }

    private func add(_ url: URL) {
        if !roots.contains(url) { roots.append(url) }
    }

    private func label(for url: URL) -> String {
        if let v = volumes.volumes.first(where: { $0.url.standardizedFileURL == url.standardizedFileURL }) {
            return "💾 " + v.name
        }
        return url.path.replacingOccurrences(of: FS.home.path, with: "~")
    }

    // MARK: Règles

    private var rulesBar: some View {
        HStack(spacing: 12) {
            Picker("Sélection auto", selection: $tools.keepRule) {
                ForEach(FileTools.KeepRule.allCases) { Text($0.rawValue).tag($0) }
            }
            .frame(width: 330)
            .onChange(of: tools.keepRule) { _, rule in
                if rule == .inFolder && tools.preferredFolder == nil { tools.preferredFolder = pickFolder() }
                tools.applyKeepRule()
            }
            if tools.keepRule == .inFolder {
                Button(tools.preferredFolder?.lastPathComponent ?? "Choisir…") {
                    if let u = pickFolder() { tools.preferredFolder = u; tools.applyKeepRule() }
                }
            }
            Picker("", selection: $kindFilter) { ForEach(kinds, id: \.self) { Text($0) } }
                .pickerStyle(.segmented).frame(width: 440)
            Spacer()
        }
        .disabled(tools.duplicates.isEmpty)
    }

    private var summary: some View {
        HStack(spacing: 12) {
            Text(tools.status).foregroundStyle(.secondary).lineLimit(1)
            if !message.isEmpty { Text(message).foregroundStyle(.green) }
            Spacer()
            Button("Tout décocher") { tools.selectAllDuplicates(false) }
            Button("Réappliquer la règle") { tools.applyKeepRule() }
            Toggle("Suppression définitive", isOn: $permanent)
                .toggleStyle(.checkbox)
                .help("Recommandé sur une clé USB ou un disque externe : la Corbeille n'y libère pas d'espace")
            Button("Supprimer \(selectedCount) copies (\(Fmt.bytes(selectedSize)))") { confirm = true }
                .buttonStyle(.borderedProminent).tint(.teal).disabled(selectedSize == 0)
        }
        .onChange(of: touchesExternal) { _, ext in if ext { permanent = true } }
    }

    // MARK: Groupe

    private func groupCard(_ g: DuplicateGroup) -> some View {
        GlassCard(padding: 12) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 10) {
                    thumbnail(g.files[0].url)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(g.files[0].name).fontWeight(.semibold).lineLimit(1)
                        Text("\(g.files[0].kind) · \(Fmt.bytes(g.size)) chacun").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    if g.files.allSatisfy(\.selected) {
                        Label("Toutes cochées : rien ne sera supprimé", systemImage: "exclamationmark.triangle.fill")
                            .font(.caption).foregroundStyle(.orange)
                    }
                    Text("\(g.files.count) copies · \(Fmt.bytes(g.wasted)) en trop")
                        .font(.caption.weight(.semibold)).foregroundStyle(.teal)
                }
                ForEach(g.files) { f in
                    HStack(spacing: 10) {
                        Button { tools.toggleDuplicate(group: g.id, file: f.id) } label: {
                            CheckCircle(on: f.selected, tint: .teal)
                        }.buttonStyle(.plain)
                        if !f.selected {
                            Text("conservé").font(.caption2).padding(.horizontal, 5).padding(.vertical, 1)
                                .background(.green.opacity(0.25), in: Capsule())
                        }
                        if !isOnMac(f.url) {
                            Label(volumeName(f.url), systemImage: "externaldrive.fill")
                                .font(.caption2).padding(.horizontal, 5).padding(.vertical, 1)
                                .background(.cyan.opacity(0.2), in: Capsule())
                        }
                        Text(f.url.path.replacingOccurrences(of: FS.home.path, with: "~"))
                            .font(.callout).lineLimit(1).truncationMode(.middle)
                        Spacer()
                        Text(Fmt.relativeDate(f.modified)).font(.caption).foregroundStyle(.secondary)
                        Button { NSWorkspace.shared.open(f.url) } label: { Image(systemName: "eye") }
                            .buttonStyle(.borderless).help("Ouvrir")
                        Button { FS.reveal(f.url) } label: { Image(systemName: "magnifyingglass") }
                            .buttonStyle(.borderless).help("Afficher dans le Finder")
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func thumbnail(_ url: URL) -> some View {
        if ["jpg", "jpeg", "png", "heic", "gif", "tiff"].contains(url.pathExtension.lowercased()) {
            ThumbnailView(url: url).frame(width: 40, height: 40)
                .clipShape(RoundedRectangle(cornerRadius: 8))
        } else {
            Image(nsImage: NSWorkspace.shared.icon(forFile: url.path)).resizable().frame(width: 36, height: 36)
        }
    }

    private func isOnMac(_ url: URL) -> Bool { !url.path.hasPrefix("/Volumes/") }

    private func volumeName(_ url: URL) -> String {
        let parts = url.pathComponents
        return parts.count > 2 ? parts[2] : "Externe"
    }
}

struct RootChip: Identifiable {
    let url: URL
    let label: String
    var id: String { url.path }
}

/// Pastilles supprimables pour la liste des emplacements.
struct FlowChips: View {
    let items: [RootChip]
    var onRemove: (URL) -> Void

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(items) { item in
                    HStack(spacing: 6) {
                        Text(item.label).font(.callout).lineLimit(1)
                        Button { onRemove(item.url) } label: { Image(systemName: "xmark.circle.fill") }
                            .buttonStyle(.plain).foregroundStyle(.secondary)
                    }
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(.white.opacity(0.08), in: Capsule())
                }
            }
        }
    }
}
