import SwiftUI
import AppKit

enum Module: String, CaseIterable, Identifiable {
    case smartScan
    case cleanup
    case security, privacy, permissions
    case monitor, activity, battery, network, disks, maintenance, launch
    case apps, updater, extensions
    case largeFiles, duplicates, similarImages, spaceMap, volumes, cloud, tidy, shredder

    var id: String { rawValue }

    var title: String {
        switch self {
        case .smartScan: "Analyse intelligente"
        case .cleanup: "Déchets système"
        case .security: "Sécurité"
        case .privacy: "Confidentialité"
        case .permissions: "Autorisations des apps"
        case .monitor: "Surveillance"
        case .activity: "Applications actives"
        case .battery: "Batterie et veille"
        case .network: "Réseau"
        case .disks: "Disques"
        case .maintenance: "Maintenance"
        case .launch: "Démarrage et arrière-plan"
        case .apps: "Désinstalleur"
        case .updater: "Mises à jour"
        case .extensions: "Extensions"
        case .largeFiles: "Gros et vieux fichiers"
        case .duplicates: "Doublons"
        case .similarImages: "Images similaires"
        case .spaceMap: "Carte de l'espace"
        case .volumes: "Supports amovibles"
        case .cloud: "Nettoyage du cloud"
        case .tidy: "Rangement"
        case .shredder: "Broyeur"
        }
    }

    var icon: String {
        switch self {
        case .smartScan: "sparkles"
        case .cleanup: "wand.and.stars"
        case .security: "shield.lefthalf.filled"
        case .privacy: "hand.raised.fill"
        case .permissions: "lock.rectangle.stack.fill"
        case .monitor: "waveform.path.ecg"
        case .activity: "rectangle.stack.fill"
        case .battery: "battery.75percent"
        case .network: "wifi"
        case .disks: "internaldrive.fill"
        case .maintenance: "wrench.and.screwdriver.fill"
        case .launch: "power.circle.fill"
        case .apps: "square.grid.2x2.fill"
        case .updater: "arrow.triangle.2.circlepath"
        case .extensions: "puzzlepiece.extension.fill"
        case .largeFiles: "doc.badge.ellipsis"
        case .duplicates: "square.on.square"
        case .similarImages: "photo.stack.fill"
        case .spaceMap: "chart.pie.fill"
        case .volumes: "externaldrive.fill"
        case .cloud: "icloud.fill"
        case .tidy: "tray.2.fill"
        case .shredder: "scissors"
        }
    }

    var tint: Color {
        switch self {
        case .smartScan: .purple
        case .cleanup: .blue
        case .security: .green
        case .privacy: .mint
        case .permissions: .indigo
        case .monitor: .green
        case .activity: .indigo
        case .battery: .mint
        case .network: .cyan
        case .disks: .blue
        case .maintenance: .orange
        case .launch: .red
        case .apps: .orange
        case .updater: .cyan
        case .extensions: .purple
        case .largeFiles: .yellow
        case .duplicates: .teal
        case .similarImages: .pink
        case .spaceMap: .pink
        case .volumes: .cyan
        case .cloud: .blue
        case .tidy: .teal
        case .shredder: .red
        }
    }

    var section: String {
        switch self {
        case .smartScan, .cleanup: ""
        case .security, .privacy, .permissions: "Protection"
        case .monitor, .activity, .battery, .network, .disks, .maintenance, .launch: "Performances"
        case .apps, .updater, .extensions: "Applications"
        case .largeFiles, .duplicates, .similarImages, .spaceMap, .volumes, .cloud, .tidy, .shredder: "Fichiers"
        }
    }

    static let sections = ["", "Protection", "Performances", "Applications", "Fichiers"]
}

struct ContentView: View {
    @EnvironmentObject var router: Router
    @EnvironmentObject var volumes: VolumeManager
    @EnvironmentObject var alerts: HealthCenter
    @EnvironmentObject var selfUpdate: SelfUpdater
    @EnvironmentObject var guardian: Guardian
    @EnvironmentObject var activity: AppActivityMonitor
    @Etat private var showNotes = false
    @Etat private var hasFDA = true
    private var current: Module { router.selection ?? .smartScan }

    var body: some View {
        NavigationSplitView {
            List(selection: $router.selection) {
                ForEach(Module.sections, id: \.self) { section in
                    let items = Module.allCases.filter { $0.section == section }
                    if section.isEmpty {
                        ForEach(items) { row($0) }
                    } else {
                        Section(section) { ForEach(items) { row($0) } }
                    }
                }
            }
            .listStyle(.sidebar)
            .navigationSplitViewColumnWidth(min: 230, ideal: 250)
            .safeAreaInset(edge: .bottom) { SidebarFooter() }
        } detail: {
            ZStack {
                AuraTheme.background(for: current)
                VStack(spacing: 0) {
                    if !hasFDA { fdaBanner }
                    if let rel = selfUpdate.available { updateBanner(rel) }
                    if let a = alerts.activeAlert { alertBanner(a) }
                    detail
                        .transition(.opacity.combined(with: .move(edge: .trailing)))
                        .id(current)
                }
            }
            .animation(.easeInOut(duration: 0.25), value: current)
        }
        .onAppear { hasFDA = FS.hasFullDiskAccess }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            let v = FS.hasFullDiskAccess
            if v != hasFDA { hasFDA = v }
        }
    }

    private func row(_ m: Module) -> some View {
        Label {
            HStack {
                Text(m.title)
                Spacer()
                if m == .activity && !activity.greedyApps.isEmpty {
                    Text("\(activity.greedyApps.count)").font(.caption2.bold())
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(.orange.opacity(0.6), in: Capsule())
                }
                if m == .security && guardian.unhandledCount > 0 {
                    Text("\(guardian.unhandledCount)").font(.caption2.bold())
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(.red.opacity(0.6), in: Capsule())
                }
                if m == .volumes && !volumes.externalVolumes.isEmpty {
                    Text("\(volumes.externalVolumes.count)").font(.caption2.bold())
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(.cyan.opacity(0.35), in: Capsule())
                }
            }
        } icon: {
            Image(systemName: m.icon)
                .foregroundStyle(.white)
                .font(.system(size: 11, weight: .bold))
                .frame(width: 22, height: 22)
                .background(m.tint.gradient, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
        }
        .tag(m)
        .padding(.vertical, 2)
    }

    private var fdaBanner: some View {
        HStack(spacing: 12) {
            Image(systemName: "lock.shield.fill").foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: 2) {
                Text("Accès complet au disque requis").fontWeight(.semibold)
                Text("Sans lui, Aura ne voit qu'une partie des fichiers (Mail, Safari, autorisations, conteneurs…).")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Button("Ouvrir les réglages") { FS.openFullDiskAccessSettings() }
                .buttonStyle(.borderedProminent).tint(.orange)
        }
        .padding(12)
        .background(.orange.opacity(0.12))
    }

    private func updateBanner(_ rel: SelfUpdater.Release) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "arrow.down.app.fill").font(.title3).foregroundStyle(AuraTheme.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text("Aura \(rel.version) est disponible").fontWeight(.semibold)
                Text(selfUpdate.isInstalling ? selfUpdate.status : "Tu as la version \(selfUpdate.currentVersion).")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if selfUpdate.isInstalling {
                ProgressView(value: selfUpdate.progress).frame(width: 140)
            }
            Spacer()
            if !rel.notes.isEmpty {
                Button("Nouveautés") { showNotes = true }
                    .popover(isPresented: $showNotes) {
                        ScrollView {
                            Text(rel.notes).padding().frame(width: 380, alignment: .leading)
                        }
                        .frame(maxHeight: 360)
                    }
            }
            Button("Installer et redémarrer") { Task { await selfUpdate.install() } }
                .buttonStyle(.borderedProminent).tint(.purple)
                .disabled(selfUpdate.isInstalling)
        }
        .padding(12)
        .background(Color.purple.opacity(0.15))
    }

    private func alertBanner(_ a: HealthAlert) -> some View {
        HStack(spacing: 12) {
            Image(systemName: a.icon).foregroundStyle(a.color)
            VStack(alignment: .leading, spacing: 2) {
                Text(a.title).fontWeight(.semibold)
                Text(a.message).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if let target = a.module {
                Button("Régler") { router.open(target) }.buttonStyle(.borderedProminent).tint(a.color)
            }
            Button { alerts.dismiss() } label: { Image(systemName: "xmark") }.buttonStyle(.borderless)
        }
        .padding(12)
        .background(a.color.opacity(0.12))
    }

    @ViewBuilder private var detail: some View {
        switch current {
        case .smartScan: SmartScanView(goTo: { router.open($0) })
        case .cleanup: CleanupView()
        case .security: SecurityView()
        case .privacy: PrivacyView()
        case .permissions: PermissionsView()
        case .monitor: MonitorView()
        case .activity: AppActivityView()
        case .battery: BatteryView()
        case .network: NetworkView()
        case .disks: DisksView()
        case .maintenance: MaintenanceView()
        case .launch: LaunchItemsView()
        case .apps: AppsView()
        case .updater: UpdaterView()
        case .extensions: ExtensionsView()
        case .largeFiles: LargeFilesView()
        case .duplicates: DuplicatesView()
        case .similarImages: SimilarImagesView()
        case .spaceMap: SpaceMapView()
        case .volumes: VolumesView()
        case .cloud: CloudView()
        case .tidy: TidyView()
        case .shredder: ShredderView()
        }
    }
}

/// Pied de la barre latérale : seul élément de la fenêtre principale qui suit
/// la surveillance en continu, pour ne pas redessiner toute la fenêtre à chaque mesure.
struct SidebarFooter: View {
    @EnvironmentObject var cleanup: CleanupEngine
    @EnvironmentObject var monitor: SystemMonitor

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Divider().opacity(0.3)
            HStack {
                Circle().fill(AuraTheme.scoreColor(monitor.healthScore)).frame(width: 8, height: 8)
                Text("Santé du Mac : \(monitor.healthScore)/100").font(.caption)
            }
            Text("Libéré au total : \(Fmt.bytes(Int64(cleanup.totalFreed)))")
                .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(12)
    }
}
