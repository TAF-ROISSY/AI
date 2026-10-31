import SwiftUI
import AppKit

struct CameraCleanerView: View {
    @EnvironmentObject var cam: CameraCleaner
    @EnvironmentObject var router: Router
    @EnvironmentObject var volumes: VolumeManager
    @Etat private var expanded: Set<CamCategory> = []
    @Etat private var confirm = false

    private var onExternal: Bool { cam.items.contains { $0.selected && $0.url.path.hasPrefix("/Volumes/") } }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .camera, subtitle: "Insta360 (X et Ace Pro), GoPro, DJI : repère les aperçus basse définition, fichiers techniques, copies et ratés qui encombrent tes dossiers de rushes.")

                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Dossiers à analyser").font(.auraHeadline)
                            Spacer()
                            Menu {
                                ForEach(volumes.externalVolumes) { v in
                                    Button { add(v.url) } label: { Label(v.name, systemImage: v.symbol) }
                                }
                                if !volumes.externalVolumes.isEmpty { Divider() }
                                Button("Choisir un dossier…") { if let u = pickFolder() { add(u) } }
                                Button("Vidéos du Mac") { add(FS.url("~/Movies")) }
                            } label: { Label("Ajouter", systemImage: "plus") }
                            .fixedSize()
                            BigButton(title: cam.isScanning ? "Analyse…" : "Analyser", icon: "sparkle.magnifyingglass",
                                      busy: cam.isScanning) { Task { await cam.analyze() } }
                                .disabled(cam.sources.isEmpty)
                        }
                        if cam.sources.isEmpty {
                            Text("Ajoute la carte SD de ta caméra ou le dossier où tu importes tes rushes.").foregroundStyle(.secondary)
                        } else {
                            FlowChips(items: cam.sources.map { RootChip(url: $0, label: label(for: $0)) }) { u in
                                cam.sources.removeAll { $0 == u }
                            }
                        }
                    }
                }

                if cam.isScanning {
                    HStack {
                        ProgressView(value: cam.progress).frame(width: 240)
                        Text(cam.status).foregroundStyle(.secondary)
                        Spacer()
                    }
                } else if !cam.status.isEmpty {
                    Text(cam.status).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                }

                if !cam.items.isEmpty || cam.scannedVideos > 0 {
                    HStack(spacing: 14) {
                        StatTile(title: "Vidéos analysées", value: "\(cam.scannedVideos)", icon: "video")
                        StatTile(title: "Poids des rushes", value: Fmt.bytes(cam.scannedBytes), icon: "internaldrive")
                        StatTile(title: "Inutiles repérés", value: Fmt.bytes(cam.totalSize), icon: "trash",
                                 tint: cam.totalSize > 0 ? AuraTheme.amber : AuraTheme.green)
                        StatTile(title: "Sélectionnés", value: Fmt.bytes(cam.selectedSize), icon: "checkmark.circle")
                    }
                }

                ForEach(CamCategory.allCases) { c in
                    let list = cam.entries(in: c)
                    if !list.isEmpty { categoryCard(c, list) }
                }

                if !cam.items.isEmpty {
                    HStack {
                        Text(onExternal
                             ? "Sur une carte SD ou un disque externe, la suppression est définitive (la Corbeille n'y libère pas de place). Sur le Mac, les fichiers vont à la Corbeille."
                             : "Les fichiers iront à la Corbeille du Mac.")
                            .font(.auraCaption).foregroundStyle(.secondary)
                        Spacer()
                        BigButton(title: "Supprimer \(Fmt.bytes(cam.selectedSize))", icon: "trash", gradient: AuraTheme.danger,
                                  busy: cam.isDeleting) { confirm = true }
                            .disabled(cam.selectedSize == 0)
                    }
                }
            }
            .padding(28)
        }
        .onAppear {
            let r = router.consumeRoots()
            if !r.isEmpty { cam.sources = r; cam.items = []; cam.status = "" }
        }
        .confirmationDialog("Supprimer \(cam.items.filter(\.selected).count) fichier(s) (\(Fmt.bytes(cam.selectedSize))) ?",
                            isPresented: $confirm) {
            Button("Supprimer", role: .destructive) { Task { await cam.deleteSelected() } }
        } message: {
            Text(onExternal ? "Les fichiers de la carte ou du disque externe seront supprimés définitivement."
                            : "Les fichiers iront à la Corbeille.")
        }
    }

    private func categoryCard(_ c: CamCategory, _ list: [CamItem]) -> some View {
        let size = list.reduce(Int64(0)) { $0 + $1.size }
        let allOn = list.allSatisfy(\.selected)
        let open = expanded.contains(c)
        return GlassCard(padding: 0) {
            VStack(spacing: 0) {
                HStack(alignment: .top, spacing: 12) {
                    Button { cam.toggleCategory(c) } label: { CheckCircle(on: allOn) }.buttonStyle(.plain)
                    Image(systemName: c.icon).font(.aura(18)).foregroundStyle(AuraTheme.legendDim).frame(width: 26)
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(spacing: 8) {
                            Text(c.title).font(.auraHeadline)
                            if !c.defaultSelected {
                                Text("à vérifier").font(.auraCaption2)
                                    .padding(.horizontal, 6).padding(.vertical, 1)
                                    .background(AuraTheme.amber.opacity(0.25), in: Capsule())
                                    .foregroundStyle(AuraTheme.amber)
                            }
                        }
                        Text(c.detail).font(.auraCaption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer(minLength: 12)
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(Fmt.bytes(size)).font(.auraReadout(20)).monospacedDigit()
                        Text("\(list.count) fichier(s)").font(.auraCaption2).foregroundStyle(.secondary)
                    }
                    Button {
                        if open { expanded.remove(c) } else { expanded.insert(c) }
                    } label: {
                        Image(systemName: "chevron.down").rotationEffect(.degrees(open ? 180 : 0))
                    }
                    .buttonStyle(.borderless)
                }
                .padding(16)

                if open {
                    Divider().opacity(0.2)
                    LazyVStack(spacing: 0) {
                        ForEach(list.prefix(400)) { item in
                            HStack(spacing: 10) {
                                Button { cam.toggle(item.id) } label: { CheckCircle(on: item.selected).font(.auraBody) }
                                    .buttonStyle(.plain)
                                if c == .shortClips || c == .duplicates {
                                    Button { NSWorkspace.shared.open(item.url) } label: { Image(systemName: "play.circle") }
                                        .buttonStyle(.borderless).help("Lire")
                                }
                                Text(item.url.lastPathComponent).lineLimit(1).truncationMode(.middle)
                                Text(item.note).font(.auraCaption).foregroundStyle(.tertiary).lineLimit(1)
                                Spacer()
                                Text(item.url.deletingLastPathComponent().path.replacingOccurrences(of: FS.home.path, with: "~"))
                                    .font(.auraCaption2).foregroundStyle(.tertiary).lineLimit(1).truncationMode(.head)
                                    .frame(maxWidth: 260, alignment: .trailing)
                                Text(Fmt.bytes(item.size)).font(.auraCaption).monospacedDigit().frame(width: 80, alignment: .trailing)
                                Button { FS.reveal(item.url) } label: { Image(systemName: "magnifyingglass") }
                                    .buttonStyle(.borderless)
                            }
                            .padding(.horizontal, 18).padding(.vertical, 5)
                        }
                        if list.count > 400 {
                            Text("+ \(list.count - 400) autres fichiers").font(.auraCaption).foregroundStyle(.tertiary).padding(8)
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
        }
    }

    private func add(_ u: URL) {
        if !cam.sources.contains(u) { cam.sources.append(u); cam.items = []; cam.status = "" }
    }

    private func label(for u: URL) -> String {
        if let v = volumes.volumes.first(where: { $0.url.standardizedFileURL == u.standardizedFileURL }) { return "💾 " + v.name }
        return u.path.replacingOccurrences(of: FS.home.path, with: "~")
    }
}
