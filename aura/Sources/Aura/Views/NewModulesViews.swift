import SwiftUI
import AppKit
import Charts

// MARK: - Protection en temps réel (carte affichée dans Sécurité)

struct GuardianCard: View {
    @EnvironmentObject var guardian: Guardian
    @EnvironmentObject var health: HealthCenter
    @Etat private var enabled = true
    @Etat private var downloads = true

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 10) {
                    Image(systemName: guardian.isActive ? "eye.circle.fill" : "eye.slash.circle")
                        .font(.auraTitle2).foregroundStyle(guardian.isActive ? AuraTheme.green : .secondary)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Protection en temps réel").font(.auraHeadline)
                        Text(guardian.isActive ? "Active : lancements automatiques\(downloads ? " et téléchargements" : "") surveillés"
                                               : "Désactivée")
                            .font(.auraCaption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Toggle("Téléchargements", isOn: Binding(get: { downloads }, set: {
                        downloads = $0; guardian.watchDownloads = $0; guardian.restart()
                    })).toggleStyle(.checkbox).disabled(!enabled)
                    Toggle("", isOn: Binding(get: { enabled }, set: {
                        enabled = $0; guardian.enabled = $0
                        if $0 { guardian.start(health: health) } else { guardian.stop() }
                    })).toggleStyle(.switch).labelsHidden()
                }
                if guardian.events.isEmpty {
                    Text("Aucun événement depuis l'ouverture d'Aura.").font(.auraCaption).foregroundStyle(.tertiary)
                } else {
                    ForEach(guardian.events.prefix(8)) { e in eventRow(e) }
                }
            }
        }
        .onAppear { enabled = guardian.enabled; downloads = guardian.watchDownloads }
    }

    private func eventRow(_ e: GuardEvent) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon(e)).foregroundStyle(color(e.level)).frame(width: 20)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(e.title).fontWeight(.medium).lineLimit(1)
                    Text(Fmt.relativeDate(e.date)).font(.auraCaption2).foregroundStyle(.tertiary)
                }
                Text(e.detail).font(.auraCaption).foregroundStyle(.secondary).lineLimit(2)
                if let o = e.origin {
                    Text("Provenance : \(URL(string: o)?.host ?? o)").font(.auraCaption2).foregroundStyle(.tertiary)
                }
            }
            Spacer()
            if e.handled {
                Text("traité").font(.auraCaption2).foregroundStyle(.secondary)
            } else {
                Button { FS.reveal(e.url) } label: { Image(systemName: "magnifyingglass") }.buttonStyle(.borderless)
                if e.level.rawValue >= GuardEvent.Level.warning.rawValue || e.kind == .launchItem {
                    Button("Supprimer") { Task { await guardian.remove(e) } }.controlSize(.small)
                }
                Button("OK") { guardian.markHandled(e.id) }.controlSize(.small)
            }
        }
        .opacity(e.handled ? 0.5 : 1)
    }

    private func icon(_ e: GuardEvent) -> String {
        e.kind == .download ? "arrow.down.circle" : "power.circle"
    }

    private func color(_ l: GuardEvent.Level) -> Color {
        switch l {
        case .ok: return AuraTheme.green
        case .info: return AuraTheme.signal
        case .warning: return AuraTheme.amber
        case .danger: return AuraTheme.red
        }
    }
}

// MARK: - Réseau

struct NetworkView: View {
    @EnvironmentObject var net: NetworkTools
    @EnvironmentObject var monitor: SystemMonitor

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .network, subtitle: "Débit réel de ta connexion et applications qui consomment le réseau.")

                GlassCard(padding: 24) {
                    HStack(spacing: 30) {
                        speedGauge("Réception", net.lastTest?.download, AuraTheme.cool)
                        speedGauge("Envoi", net.lastTest?.upload, AuraTheme.signal)
                        VStack(alignment: .leading, spacing: 8) {
                            if let t = net.lastTest {
                                if let l = t.latency { Label(String(format: "Latence %.0f ms", l), systemImage: "timer") }
                                if let r = t.responsiveness { Label("Réactivité \(r.lowercased())", systemImage: "bolt.horizontal") }
                                if let i = t.interface { Label("Interface \(i)", systemImage: "network") }
                                Text("Mesuré \(Fmt.relativeDate(t.date))").font(.auraCaption).foregroundStyle(.secondary)
                            } else {
                                Text("Mesure le vrai débit de ta connexion avec l'outil d'Apple (environ 20 secondes).")
                                    .foregroundStyle(.secondary)
                            }
                            if !net.error.isEmpty { Text(net.error).foregroundStyle(AuraTheme.red).font(.auraCaption) }
                            BigButton(title: net.isTesting ? "Test en cours…" : "Tester le débit", icon: "speedometer",
                                      busy: net.isTesting) { Task { await net.runSpeedTest() } }
                        }
                        Spacer()
                    }
                }

                HStack(alignment: .top, spacing: 14) {
                    GlassCard {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Wi-Fi").fontWeight(.semibold)
                                Spacer()
                                Button { Task { await net.readWifi() } } label: { Image(systemName: "arrow.clockwise") }.buttonStyle(.borderless)
                            }
                            if net.wifi.isEmpty {
                                Text("Non connecté en Wi-Fi, ou informations indisponibles.").font(.auraCaption).foregroundStyle(.secondary)
                            }
                            ForEach(net.wifi.keys.sorted(), id: \.self) { k in
                                HStack { Text(k).foregroundStyle(.secondary); Spacer(); Text(net.wifi[k] ?? "") }.font(.auraCallout)
                            }
                            Divider().opacity(0.2)
                            HStack {
                                Label(Fmt.rate(monitor.netIn), systemImage: "arrow.down").foregroundStyle(AuraTheme.cool)
                                Spacer()
                                Label(Fmt.rate(monitor.netOut), systemImage: "arrow.up").foregroundStyle(AuraTheme.signal)
                            }
                            .font(.auraCallout)
                        }
                    }
                    .frame(width: 340)

                    GlassCard {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Consommation par application").fontWeight(.semibold)
                                Spacer()
                                if net.isMeasuring { ProgressView().controlSize(.small) }
                                Button("Mesurer") { Task { await net.measureUsage() } }.disabled(net.isMeasuring)
                            }
                            Text("Données échangées depuis le lancement de chaque app.").font(.auraCaption).foregroundStyle(.secondary)
                            let maxTotal = Double(net.usage.first?.total ?? 1)
                            ForEach(net.usage) { u in
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack {
                                        Text(u.name).lineLimit(1)
                                        Spacer()
                                        Text("↓ \(Fmt.bytes(u.received))  ↑ \(Fmt.bytes(u.sent))")
                                            .font(.auraCaption.monospacedDigit()).foregroundStyle(.secondary)
                                    }
                                    GeometryReader { g in
                                        Capsule().fill(Color.cyan.gradient)
                                            .frame(width: max(2, g.size.width * Double(u.total) / max(1, maxTotal)), height: 4)
                                    }
                                    .frame(height: 4)
                                }
                            }
                        }
                    }
                }

                if net.history.count > 1 {
                    GlassCard {
                        VStack(alignment: .leading) {
                            Text("Historique des tests").fontWeight(.semibold)
                            Chart(net.history.reversed(), id: \.date) { t in
                                LineMark(x: .value("Date", t.date), y: .value("Mb/s", t.download / 1_000_000), series: .value("Sens", "Réception"))
                                    .foregroundStyle(AuraTheme.cool)
                                LineMark(x: .value("Date", t.date), y: .value("Mb/s", t.upload / 1_000_000), series: .value("Sens", "Envoi"))
                                    .foregroundStyle(AuraTheme.signal)
                            }
                            .frame(height: 140)
                        }
                    }
                }
            }
            .padding(28)
        }
        .task { if net.wifi.isEmpty { await net.readWifi() } }
    }

    private func speedGauge(_ label: String, _ bps: Double?, _ color: Color) -> some View {
        let mbps = (bps ?? 0) / 1_000_000
        return RingGauge(value: min(1, mbps / 1000), label: bps == nil ? "—" : String(format: "%.0f", mbps),
                         caption: "\(label) Mb/s", color: color, size: 130, lineWidth: 12)
    }
}

// MARK: - Disques

struct DisksView: View {
    @EnvironmentObject var disks: DiskTools

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .disks, subtitle: "État de santé (SMART) et vitesse réelle de tes disques internes et externes.")
                HStack {
                    if !disks.message.isEmpty { Text(disks.message).foregroundStyle(AuraTheme.amber) }
                    Spacer()
                    Button { Task { await disks.load() } } label: { Label("Actualiser", systemImage: "arrow.clockwise") }
                }
                if disks.isLoading && disks.disks.isEmpty {
                    ProgressView("Lecture des disques…").padding(40)
                }
                ForEach(disks.disks) { d in diskCard(d) }
            }
            .padding(28)
        }
        .task { if disks.disks.isEmpty { await disks.load() } }
    }

    private func diskCard(_ d: PhysicalDisk) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 14) {
                    Image(systemName: d.isInternal ? "internaldrive.fill" : "externaldrive.fill")
                        .font(.aura(34, .light)).foregroundStyle(d.isInternal ? AuraTheme.signal : AuraTheme.cool)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(d.name).font(.auraTitle3.bold())
                        Text("\(Fmt.bytes(d.size)) · \(d.isSSD ? "SSD" : "Disque mécanique") · \(d.protocolName) · \(d.id)")
                            .font(.auraCaption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Label(d.smartOK == true ? "En bonne santé" : d.smartOK == false ? "DÉFAILLANT : sauvegarde vite !" : "SMART non disponible",
                              systemImage: d.smartOK == true ? "checkmark.seal.fill" : d.smartOK == false ? "exclamationmark.octagon.fill" : "questionmark.circle")
                            .foregroundStyle(d.smartOK == true ? AuraTheme.green : d.smartOK == false ? AuraTheme.red : .secondary)
                            .fontWeight(.semibold)
                        Text("Statut SMART : \(d.smart)").font(.auraCaption2).foregroundStyle(.tertiary)
                    }
                }
                ForEach(d.volumes) { v in
                    HStack(spacing: 12) {
                        Text(v.name).frame(width: 180, alignment: .leading).lineLimit(1)
                        ProgressView(value: v.usedRatio).tint(AuraTheme.loadColor(v.usedRatio))
                        Text("\(Fmt.bytes(v.free)) libres").font(.auraCaption).foregroundStyle(.secondary).frame(width: 110, alignment: .trailing)
                        if disks.benchmarking == v.id {
                            ProgressView().controlSize(.small).frame(width: 190)
                        } else if let b = disks.benchmarks[v.id] {
                            Text("✍︎ \(Fmt.rate(b.write))  ·  👁 \(Fmt.rate(b.read))")
                                .font(.auraCaption.monospacedDigit()).frame(width: 190)
                        } else {
                            Button("Tester la vitesse") { Task { await disks.benchmark(v) } }
                                .controlSize(.small).frame(width: 190)
                                .disabled(disks.benchmarking != nil || v.isReadOnly)
                        }
                    }
                }
                if d.volumes.contains(where: { disks.benchmarks[$0.id] != nil }) {
                    Text("Test : écriture puis lecture d'un fichier de 1 Go sans cache, supprimé ensuite.")
                        .font(.auraCaption2).foregroundStyle(.tertiary)
                }
            }
        }
    }
}

// MARK: - Batterie

struct BatteryView: View {
    @EnvironmentObject var monitor: SystemMonitor
    @EnvironmentObject var history: BatteryHistory
    @EnvironmentObject var awake: KeepAwake

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .battery, subtitle: "Santé de la batterie dans le temps, et mode « Rester éveillé ».")
                let b = monitor.battery
                if b.present {
                    HStack(spacing: 14) {
                        GlassCard {
                            VStack(spacing: 8) {
                                RingGauge(value: b.level, label: Fmt.percent(b.level), color: b.level > 0.2 ? AuraTheme.green : AuraTheme.red, size: 110, lineWidth: 11)
                                Text(b.isCharging ? "En charge" : b.onAC ? "Sur secteur" : "Sur batterie").fontWeight(.semibold)
                                if let t = b.timeRemaining, !b.onAC {
                                    Text("\(t / 60) h \(t % 60) min restantes").font(.auraCaption).foregroundStyle(.secondary)
                                }
                            }
                            .frame(maxWidth: .infinity)
                        }
                        GlassCard {
                            VStack(spacing: 8) {
                                RingGauge(value: b.health ?? 0, label: b.health.map(Fmt.percent) ?? "—",
                                          color: (b.health ?? 1) > 0.8 ? AuraTheme.green : AuraTheme.amber, size: 110, lineWidth: 11)
                                Text("Capacité maximale").fontWeight(.semibold)
                                Text("par rapport à une batterie neuve").font(.auraCaption).foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                        }
                        GlassCard {
                            VStack(alignment: .leading, spacing: 8) {
                                Label("\(b.cycleCount ?? 0) cycles de charge", systemImage: "arrow.triangle.2.circlepath")
                                if let t = b.temperature { Label(String(format: "%.0f °C", t), systemImage: "thermometer.medium") }
                                if let loss = history.monthlyLoss {
                                    Label(String(format: "Usure : %.1f %% par mois", loss * 100), systemImage: "chart.line.downtrend.xyaxis")
                                }
                                Text(advice(b)).font(.auraCaption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    GlassCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Santé dans le temps").fontWeight(.semibold)
                            if history.snapshots.count < 2 {
                                Text("Aura enregistre un relevé par jour : la courbe se dessinera au fil des semaines.")
                                    .font(.auraCaption).foregroundStyle(.secondary)
                            } else {
                                Chart(history.snapshots) { s in
                                    LineMark(x: .value("Date", s.date), y: .value("Santé", s.health * 100))
                                        .foregroundStyle(AuraTheme.green).interpolationMethod(.catmullRom)
                                    AreaMark(x: .value("Date", s.date), y: .value("Santé", s.health * 100))
                                        .foregroundStyle(LinearGradient(colors: [AuraTheme.green.opacity(0.3), .clear], startPoint: .top, endPoint: .bottom))
                                }
                                .chartYScale(domain: 60...100)
                                .frame(height: 160)
                            }
                        }
                    }
                } else {
                    GlassCard {
                        EmptyState(icon: "powerplug", title: "Mac de bureau",
                                   message: "Pas de batterie sur ce Mac : seul le mode « Rester éveillé » s'applique.")
                    }
                }
                KeepAwakeCard()
            }
            .padding(28)
        }
    }

    private func advice(_ b: BatteryInfo) -> String {
        guard let h = b.health else { return "" }
        if h < 0.8 { return "Sous 80 %, Apple considère la batterie usée : un remplacement redonnera toute l'autonomie." }
        if b.onAC && b.level > 0.95 {
            return "Branché en permanence ? Active « Recharge optimisée » dans Réglages › Batterie pour ménager la batterie."
        }
        return "Batterie en bon état. L'idéal : rester entre 20 et 80 % au quotidien."
    }
}

struct KeepAwakeCard: View {
    @EnvironmentObject var awake: KeepAwake

    var body: some View {
        GlassCard {
            HStack(spacing: 14) {
                Image(systemName: awake.isActive ? "cup.and.saucer.fill" : "moon.zzz.fill")
                    .font(.aura(30, .light)).foregroundStyle(awake.isActive ? AuraTheme.amber : .secondary)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Rester éveillé").font(.auraHeadline)
                    Text(awake.isActive ? (awake.until.map { "Actif jusqu'à \($0.formatted(date: .omitted, time: .shortened))" } ?? "Actif jusqu'à désactivation")
                                        : "Empêche la mise en veille pendant un téléchargement, une présentation ou une copie.")
                        .font(.auraCaption).foregroundStyle(.secondary)
                }
                Spacer()
                if awake.isActive {
                    Button("Arrêter") { awake.deactivate() }.buttonStyle(AuraButton(.primary))
                } else {
                    ForEach([(30, "30 min"), (60, "1 h"), (180, "3 h")], id: \.0) { m in
                        Button(m.1) { awake.activate(minutes: m.0) }
                    }
                    Button("Sans limite") { awake.activate(minutes: nil) }
                }
            }
        }
    }
}

// MARK: - Rangement

struct TidyView: View {
    @EnvironmentObject var tidy: TidyManager
    @Etat private var desktop = true
    @Etat private var downloads = true
    @Etat private var mode: TidyMode = .byType
    @Etat private var archiveDays = 30
    @Etat private var autoWeekly = false

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .tidy, subtitle: "Range le Bureau et les Téléchargements dans des dossiers. Rien n'est supprimé, tout s'annule.")
            GlassCard(padding: 16) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 20) {
                        Toggle("Bureau", isOn: Binding(get: { desktop }, set: { desktop = $0; tidy.desktop = $0 }))
                        Toggle("Téléchargements", isOn: Binding(get: { downloads }, set: { downloads = $0; tidy.downloads = $0 }))
                        Picker("Classer", selection: Binding(get: { mode }, set: { mode = $0; tidy.mode = $0 })) {
                            ForEach(TidyMode.allCases) { Text($0.rawValue).tag($0) }
                        }
                        .frame(width: 330)
                    }
                    .toggleStyle(.checkbox)
                    HStack(spacing: 20) {
                        Picker("Archiver par mois ce qui a plus de", selection: Binding(get: { archiveDays }, set: { archiveDays = $0; tidy.archiveDays = $0 })) {
                            Text("jamais").tag(0)
                            Text("30 jours").tag(30)
                            Text("90 jours").tag(90)
                            Text("1 an").tag(365)
                        }
                        .frame(width: 400)
                        Toggle("Ranger automatiquement chaque semaine", isOn: Binding(get: { autoWeekly }, set: { autoWeekly = $0; tidy.autoWeekly = $0 }))
                            .toggleStyle(.switch)
                        Spacer()
                    }
                    HStack {
                        Text("Les fichiers ouverts ces 10 dernières minutes et les dossiers sont laissés en place.")
                            .font(.auraCaption).foregroundStyle(.secondary)
                        Spacer()
                        if !tidy.lastBatch.isEmpty {
                            Button("Annuler le dernier rangement (\(tidy.lastBatch.count))") { Task { await tidy.undo() } }
                        }
                        Button("Aperçu") { Task { await tidy.preview() } }.disabled(tidy.isWorking || (!desktop && !downloads))
                        BigButton(title: "Ranger \(tidy.plan.count) fichier(s)", icon: "tray.2.fill", busy: tidy.isWorking) {
                            Task { await tidy.apply() }
                        }
                        .disabled(tidy.plan.isEmpty)
                    }
                }
            }
            if !tidy.message.isEmpty { Text(tidy.message).foregroundStyle(AuraTheme.green).frame(maxWidth: .infinity, alignment: .leading) }
            GlassCard(padding: 10) {
                if tidy.plan.isEmpty {
                    EmptyState(icon: "tray.2", title: "Clique sur « Aperçu »",
                               message: "Aura te montre d'abord où chaque fichier ira. Tu retires ceux à laisser en place, puis tu ranges.")
                } else {
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(tidy.plan) { m in
                                HStack(spacing: 10) {
                                    Image(nsImage: NSWorkspace.shared.icon(forFile: m.from)).resizable().frame(width: 22, height: 22)
                                    Text(m.fileName).lineLimit(1).truncationMode(.middle)
                                    Spacer()
                                    Image(systemName: "arrow.right").font(.auraCaption).foregroundStyle(.secondary)
                                    Label(m.destinationFolder, systemImage: "folder.fill").font(.auraCallout).foregroundStyle(AuraTheme.signal)
                                        .frame(width: 170, alignment: .leading)
                                    Button { tidy.remove(m) } label: { Image(systemName: "xmark.circle") }
                                        .buttonStyle(.borderless).help("Laisser ce fichier en place")
                                }
                                .padding(.vertical, 5).padding(.horizontal, 6)
                                Divider().opacity(0.1)
                            }
                        }
                    }
                }
            }
        }
        .padding(28)
        .onAppear {
            desktop = tidy.desktop; downloads = tidy.downloads; mode = tidy.mode
            archiveDays = tidy.archiveDays; autoWeekly = tidy.autoWeekly
        }
    }
}
