import SwiftUI
import AppKit
import UniformTypeIdentifiers
import ImageIO

// MARK: - Images similaires

struct SimilarImagesView: View {
    @EnvironmentObject var finder: SimilarImageFinder
    @EnvironmentObject var router: Router
    @Etat private var roots: [URL] = [FS.url("~/Pictures"), FS.url("~/Downloads"), FS.url("~/Desktop")].filter(FS.exists)
    @Etat private var confirm = false
    @Etat private var message = ""

    private var selectedSize: Int64 { finder.groups.reduce(Int64(0)) { $0 + $1.reclaimable } }

    var body: some View {
        VStack(spacing: 16) {
            ModuleHeader(module: .similarImages, subtitle: "Rafales, captures en double, versions retouchées : garde seulement la meilleure.")
            GlassCard(padding: 14) {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Button { if let u = pickFolder() { if !roots.contains(u) { roots.append(u) } } } label: { Label("Ajouter un dossier", systemImage: "plus") }
                        VStack(alignment: .leading, spacing: 0) {
                            Text("Ressemblance : \(finder.strictness < 3 ? "quasi identiques" : finder.strictness < 8 ? "très proches" : "proches")")
                                .font(.auraCaption)
                            Slider(value: $finder.strictness, in: 0...14, step: 1).frame(width: 200)
                        }
                        Spacer()
                        BigButton(title: finder.isBusy ? "Analyse…" : "Chercher", icon: "photo.stack", busy: finder.isBusy) {
                            Task { await finder.scan(roots: roots) }
                        }
                        .disabled(roots.isEmpty)
                    }
                    FlowChips(items: roots.map { RootChip(url: $0, label: $0.path.replacingOccurrences(of: FS.home.path, with: "~")) }) { u in
                        roots.removeAll { $0 == u }
                    }
                    Text("La photothèque Photos n'est jamais modifiée : utilise l'album « Doublons » intégré à Photos pour elle.")
                        .font(.auraCaption).foregroundStyle(.secondary)
                }
            }
            if finder.isBusy {
                ProgressView(value: finder.progress) { Text(finder.status).font(.auraCaption) }
            }
            HStack {
                Text(finder.isBusy ? "" : finder.status).foregroundStyle(.secondary)
                if !message.isEmpty { Text(message).foregroundStyle(AuraTheme.green) }
                Spacer()
                Button("Envoyer \(Fmt.bytes(selectedSize)) à la Corbeille") { confirm = true }
                    .buttonStyle(AuraButton(.primary)).disabled(selectedSize == 0)
            }
            if finder.groups.isEmpty && !finder.isBusy {
                GlassCard { EmptyState(icon: "photo.stack", title: "Aucune série pour l'instant", message: "Aura compare le contenu visuel des images, même renommées ou redimensionnées.") }
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(finder.groups) { g in
                            GlassCard(padding: 12) {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("\(g.images.count) images similaires · \(Fmt.bytes(g.reclaimable)) à récupérer")
                                        .font(.auraCaption.weight(.semibold)).foregroundStyle(AuraTheme.signal)
                                    ScrollView(.horizontal, showsIndicators: false) {
                                        HStack(spacing: 10) {
                                            ForEach(g.images) { img in imageTile(img, group: g.id) }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        .padding(28)
        .onAppear { let r = router.consumeRoots(); if !r.isEmpty { roots = r } }
        .confirmationDialog("Envoyer les images cochées à la Corbeille ?", isPresented: $confirm) {
            Button("Envoyer à la Corbeille", role: .destructive) {
                Task { let f = await finder.removeSelected(); message = "\(Fmt.bytes(f)) envoyés à la Corbeille" }
            }
        } message: { Text("Au moins une image de chaque série est toujours conservée.") }
    }

    private func imageTile(_ img: SimilarImage, group: UUID) -> some View {
        VStack(spacing: 4) {
            ZStack(alignment: .topLeading) {
                ThumbnailView(url: img.url)
                    .frame(width: 150, height: 110)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(img.selected ? Color.pink : Color.green, lineWidth: 2))
                Button { finder.toggle(group: group, image: img.id) } label: { CheckCircle(on: img.selected, tint: AuraTheme.signal) }
                    .buttonStyle(.plain).padding(6)
                if !img.selected {
                    Text("conservée").font(.auraCaption2.bold()).padding(.horizontal, 6).padding(.vertical, 2)
                        .background(AuraTheme.green, in: Capsule()).foregroundStyle(.white)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing).padding(6)
                }
            }
            .frame(width: 150, height: 110)
            .onTapGesture(count: 2) { NSWorkspace.shared.open(img.url) }
            Text(img.name).font(.auraCaption2).lineLimit(1).truncationMode(.middle).frame(width: 150)
            Text("\(img.pixels / 1_000_000 > 0 ? "\(img.pixels / 1_000_000) Mpx" : "\(img.pixels / 1000) kpx") · \(Fmt.bytes(img.size))")
                .font(.auraCaption2).foregroundStyle(.secondary)
        }
        .contextMenu {
            Button("Ouvrir") { NSWorkspace.shared.open(img.url) }
            Button("Afficher dans le Finder") { FS.reveal(img.url) }
        }
    }
}

/// Vignette chargée en arrière-plan (évite de bloquer le défilement).
struct ThumbnailView: View {
    let url: URL
    @Etat private var image: NSImage? = nil
    var body: some View {
        ZStack {
            Color.white.opacity(0.05)
            if let image { Image(nsImage: image).resizable().scaledToFill() }
            else { ProgressView().controlSize(.small) }
        }
        .task(id: url) {
            image = await Task.detached(priority: .utility) { () -> NSImage? in
                guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
                      let cg = CGImageSourceCreateThumbnailAtIndex(src, 0, [
                        kCGImageSourceCreateThumbnailFromImageAlways: true,
                        kCGImageSourceThumbnailMaxPixelSize: 320,
                        kCGImageSourceCreateThumbnailWithTransform: true] as CFDictionary) else { return nil }
                return NSImage(cgImage: cg, size: .zero)
            }.value
        }
    }
}

// MARK: - Cloud

struct CloudView: View {
    @EnvironmentObject var cloud: CloudManager
    @Etat private var selected: String? = nil
    @Etat private var confirmDelete = false

    private var provider: CloudProvider? {
        cloud.providers.first { $0.id == selected } ?? cloud.providers.first
    }

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .cloud, subtitle: "iCloud Drive, Google Drive, OneDrive, Dropbox : libère le Mac sans rien perdre en ligne.")
            HStack {
                if !cloud.message.isEmpty { Text(cloud.message).foregroundStyle(AuraTheme.green).lineLimit(2) }
                Spacer()
                Button { Task { await cloud.scan() } } label: { Label("Analyser", systemImage: "arrow.clockwise") }
                    .disabled(cloud.isScanning)
            }
            if cloud.isScanning {
                ProgressView("Mesure de l'espace occupé par le cloud…").padding(40)
            } else if cloud.providers.isEmpty {
                GlassCard { EmptyState(icon: "icloud.slash", title: "Aucun cloud détecté", message: "Connecte iCloud Drive, Google Drive, OneDrive ou Dropbox pour les retrouver ici.") }
            } else {
                HStack(spacing: 12) {
                    ForEach(cloud.providers) { p in
                        Button { selected = p.id } label: {
                            GlassCard(padding: 14) {
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack { Image(systemName: p.icon).foregroundStyle(AuraTheme.legendDim); Text(p.name).fontWeight(.semibold).lineLimit(1) }
                                    Text("\(Fmt.bytes(p.local)) sur le Mac").font(.auraTitle3.bold())
                                    Text("sur \(Fmt.bytes(p.logical)) dans le cloud").font(.auraCaption).foregroundStyle(.secondary)
                                    ProgressView(value: Double(p.local), total: Double(max(1, p.logical))).tint(AuraTheme.signal)
                                }
                            }
                            .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(provider?.id == p.id ? Color.blue : .clear, lineWidth: 2))
                        }
                        .buttonStyle(.plain)
                    }
                }
                if let p = provider { filesCard(p) }
            }
        }
        .padding(28)
        .task { if cloud.providers.isEmpty { await cloud.scan() } }
        .confirmationDialog("Supprimer ces fichiers du Mac ET du cloud ?", isPresented: $confirmDelete) {
            Button("Supprimer partout", role: .destructive) {
                if let p = provider { Task { await cloud.deleteSelected(provider: p.id) } }
            }
        } message: { Text("Ils iront dans la Corbeille du Mac et la corbeille du service en ligne.") }
    }

    private func filesCard(_ p: CloudProvider) -> some View {
        let sel = p.files.filter(\.selected)
        return GlassCard(padding: 10) {
            VStack(spacing: 8) {
                HStack {
                    Text("Fichiers téléchargés sur le Mac").fontWeight(.semibold)
                    Spacer()
                    Button("Cocher ceux non ouverts depuis 3 mois") { cloud.selectUnused(provider: p.id) }
                    Button("Supprimer partout") { confirmDelete = true }.disabled(sel.isEmpty)
                    Button("Libérer \(Fmt.bytes(sel.reduce(Int64(0)) { $0 + $1.localSize })) sur le Mac") {
                        Task { await cloud.evictSelected(provider: p.id) }
                    }
                    .buttonStyle(AuraButton(.primary)).disabled(sel.isEmpty)
                }
                if p.files.isEmpty {
                    EmptyState(icon: "checkmark.icloud", title: "Rien de lourd en local", message: "Les fichiers de ce cloud ne prennent presque pas de place sur le Mac.")
                } else {
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(p.files) { f in
                                HStack(spacing: 10) {
                                    Button { cloud.toggle(provider: p.id, file: f.id) } label: { CheckCircle(on: f.selected, tint: AuraTheme.signal) }.buttonStyle(.plain)
                                    Image(nsImage: NSWorkspace.shared.icon(forFile: f.url.path)).resizable().frame(width: 22, height: 22)
                                    Text(f.url.path.replacingOccurrences(of: p.root.path + "/", with: "")).lineLimit(1).truncationMode(.middle)
                                    Spacer()
                                    Text("ouvert \(Fmt.relativeDate(f.accessed))").font(.auraCaption).foregroundStyle(.secondary)
                                    Text(Fmt.bytes(f.localSize)).font(.auraCallout.monospacedDigit()).frame(width: 80, alignment: .trailing)
                                }
                                .padding(.vertical, 5)
                                Divider().opacity(0.1)
                            }
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Broyeur

struct ShredderView: View {
    @Etat private var files: [URL] = []
    @Etat private var passes = 1
    @Etat private var confirm = false
    @Etat private var isShredding = false
    @Etat private var message = ""
    @Etat private var dropHover = false

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .shredder, subtitle: "Supprime définitivement des fichiers sensibles, sans passer par la Corbeille.")
            GlassCard(padding: 28) {
                VStack(spacing: 14) {
                    Image(systemName: "scissors").font(.aura(50, .light)).foregroundStyle(AuraTheme.danger)
                        .symbolEffect(.bounce, value: files.count)
                    Text("Dépose ici les fichiers ou dossiers à broyer").font(.auraTitle3.weight(.semibold))
                    Button("Choisir…") {
                        let panel = NSOpenPanel()
                        panel.canChooseDirectories = true
                        panel.allowsMultipleSelection = true
                        if panel.runModal() == .OK { add(panel.urls) }
                    }
                }
                .frame(maxWidth: .infinity, minHeight: 200)
                .background(RoundedRectangle(cornerRadius: 16).strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [8]))
                    .foregroundStyle(dropHover ? Color.red : Color.white.opacity(0.2)))
                .onDrop(of: [UTType.fileURL], isTargeted: $dropHover) { providers in
                    for p in providers {
                        _ = p.loadObject(ofClass: URL.self) { url, _ in
                            if let url { DispatchQueue.main.async { add([url]) } }
                        }
                    }
                    return true
                }
            }

            if !files.isEmpty {
                GlassCard {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(files, id: \.self) { u in
                            HStack {
                                Image(nsImage: NSWorkspace.shared.icon(forFile: u.path)).resizable().frame(width: 22, height: 22)
                                Text(u.path.replacingOccurrences(of: FS.home.path, with: "~")).lineLimit(1).truncationMode(.middle)
                                Spacer()
                                Button { files.removeAll { $0 == u } } label: { Image(systemName: "xmark.circle.fill") }.buttonStyle(.plain)
                            }
                        }
                    }
                }
            }

            HStack {
                Picker("Passes d'écrasement", selection: $passes) {
                    Text("1 passe (rapide)").tag(1)
                    Text("3 passes").tag(3)
                    Text("7 passes").tag(7)
                }
                .frame(width: 280)
                if !message.isEmpty { Text(message).foregroundStyle(AuraTheme.green) }
                Spacer()
                BigButton(title: isShredding ? "Broyage…" : "Broyer \(files.count) élément(s)", icon: "scissors",
                          gradient: AuraTheme.danger, busy: isShredding) { confirm = true }
                    .disabled(files.isEmpty)
            }
            Text("Sur un SSD, macOS répartit les écritures : l'écrasement rend la récupération très difficile mais pas impossible. Pour une protection totale, active FileVault.")
                .font(.auraCaption).foregroundStyle(.secondary)
            Spacer()
        }
        .padding(28)
        .confirmationDialog("Broyer définitivement \(files.count) élément(s) ?", isPresented: $confirm) {
            Button("Broyer", role: .destructive) {
                isShredding = true
                let list = files, p = passes
                Task {
                    let ok = await Task.detached { list.filter { Shredder.shred($0, passes: p) }.count }.value
                    message = "\(ok) élément(s) détruit(s)"
                    files = []
                    isShredding = false
                }
            }
        } message: { Text("Cette opération est irréversible.") }
    }

    private func add(_ urls: [URL]) {
        for u in urls where !files.contains(u) { files.append(u) }
    }
}
