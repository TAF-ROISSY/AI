import SwiftUI
import AppKit

/// Sélecteur de dossier partagé par les modules Fichiers.
func pickFolder(start: URL = FS.home) -> URL? {
    let panel = NSOpenPanel()
    panel.canChooseDirectories = true
    panel.canChooseFiles = false
    panel.allowsMultipleSelection = false
    panel.directoryURL = start
    panel.prompt = "Choisir"
    return panel.runModal() == .OK ? panel.url : nil
}

struct LargeFilesView: View {
    @EnvironmentObject var tools: FileTools
    @EnvironmentObject var router: Router
    @Etat private var root = FS.home
    @Etat private var ageDays = 0
    @Etat private var minMB: Double = 200
    @Etat private var kindFilter = "Tous"
    @Etat private var confirm = false
    @Etat private var message = ""

    private let kinds = ["Tous", "Vidéo", "Image", "Archive", "Audio", "Document", "Autre"]

    private var shown: [FileEntry] {
        let limit = Date().addingTimeInterval(-Double(ageDays) * 86400)
        return tools.largeFiles.filter {
            (kindFilter == "Tous" || $0.kind == kindFilter) && (ageDays == 0 || ($0.modified ?? .distantPast) < limit)
        }
    }
    private var selectedSize: Int64 { tools.largeFiles.filter(\.selected).reduce(0) { $0 + $1.size } }

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .largeFiles, subtitle: "Les fichiers les plus volumineux et les plus anciens, triés pour toi.")
            GlassCard(padding: 14) {
                HStack(spacing: 14) {
                    Button { if let u = pickFolder(start: root) { root = u } } label: {
                        Label(root.lastPathComponent, systemImage: "folder")
                    }
                    Text("Taille min. \(Int(minMB)) Mo").monospacedDigit().frame(width: 140)
                    Slider(value: $minMB, in: 50...5000, step: 50).frame(width: 200)
                    Spacer()
                    BigButton(title: tools.isBusy ? "\(tools.scannedCount) fichiers…" : "Rechercher",
                              icon: "magnifyingglass", busy: tools.isBusy) {
                        Task { await tools.findLargeFiles(in: root, minSize: Int64(minMB) * 1_000_000) }
                    }
                }
            }
            HStack {
                Picker("", selection: $kindFilter) { ForEach(kinds, id: \.self) { Text($0) } }
                    .pickerStyle(.segmented).frame(width: 520)
                Picker("Âge", selection: $ageDays) {
                    Text("Tous âges").tag(0)
                    Text("+ 6 mois").tag(180)
                    Text("+ 1 an").tag(365)
                    Text("+ 3 ans").tag(1095)
                }
                .frame(width: 170)
                Spacer()
                if !message.isEmpty { Text(message).foregroundStyle(AuraTheme.green) }
                Button("Envoyer \(Fmt.bytes(selectedSize)) à la Corbeille") { confirm = true }
                    .buttonStyle(AuraButton(.danger)).disabled(selectedSize == 0)
            }
            GlassCard(padding: 10) {
                if tools.largeFiles.isEmpty {
                    EmptyState(icon: "doc.badge.ellipsis", title: tools.isBusy ? "Recherche…" : "Aucun résultat",
                               message: "Choisis un dossier et une taille minimale, puis lance la recherche.")
                } else {
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(shown) { f in
                                let idx = tools.largeFiles.firstIndex(where: { $0.id == f.id })
                                HStack(spacing: 10) {
                                    if let idx {
                                        Toggle("", isOn: $tools.largeFiles[idx].selected).labelsHidden().toggleStyle(.checkbox)
                                    }
                                    Image(nsImage: NSWorkspace.shared.icon(forFile: f.url.path)).resizable().frame(width: 24, height: 24)
                                    VStack(alignment: .leading, spacing: 1) {
                                        Text(f.name).lineLimit(1).truncationMode(.middle)
                                        Text(f.url.deletingLastPathComponent().path.replacingOccurrences(of: FS.home.path, with: "~"))
                                            .font(.auraCaption2).foregroundStyle(.secondary).lineLimit(1).truncationMode(.head)
                                    }
                                    Spacer()
                                    Text(f.kind).font(.auraCaption).foregroundStyle(.secondary).frame(width: 70)
                                    Text(Fmt.relativeDate(f.modified)).font(.auraCaption).foregroundStyle(.secondary).frame(width: 110)
                                    Text(Fmt.bytes(f.size)).font(.auraCallout.monospacedDigit().weight(.semibold)).frame(width: 90, alignment: .trailing)
                                    Button { FS.reveal(f.url) } label: { Image(systemName: "magnifyingglass") }.buttonStyle(.borderless)
                                }
                                .padding(.vertical, 6).padding(.horizontal, 6)
                                Divider().opacity(0.12)
                            }
                        }
                    }
                }
            }
        }
        .padding(28)
        .onAppear {
            if let r = router.consumeRoots().first {
                root = r
                Task { await tools.findLargeFiles(in: r, minSize: Int64(minMB) * 1_000_000) }
            }
        }
        .confirmationDialog("Envoyer \(Fmt.bytes(selectedSize)) à la Corbeille ?", isPresented: $confirm) {
            Button("Envoyer à la Corbeille", role: .destructive) {
                Task {
                    let freed = await tools.removeLargeFiles()
                    message = "\(Fmt.bytes(freed)) envoyés à la Corbeille"
                }
            }
        }
    }
}
