import SwiftUI
import AppKit
import Charts

struct MonitorView: View {
    @EnvironmentObject var monitor: SystemMonitor
    @Etat private var sortByMemory = false
    @Etat private var search = ""
    @Etat private var processToKill: ProcessInfoRow? = nil

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .monitor, subtitle: "Processeur, mémoire, disque, réseau et batterie en temps réel.")

                HStack(spacing: 14) {
                    gaugeCard("Processeur", monitor.cpuUsage, Fmt.percent(monitor.cpuUsage), "\(monitor.cpuPerCore.count) cœurs")
                    gaugeCard("Mémoire", monitor.memPressure, Fmt.percent(monitor.memPressure),
                              "\(Fmt.bytes(monitor.memUsed)) / \(Fmt.bytes(monitor.memTotal))")
                    gaugeCard("Disque", monitor.diskUsedRatio, Fmt.percent(monitor.diskUsedRatio),
                              "\(Fmt.bytes(monitor.diskFree)) libres")
                    batteryCard
                }

                HStack(alignment: .top, spacing: 14) {
                    chartCard(title: "Processeur (%)", data: monitor.cpuHistory, color: AuraTheme.signal, maxY: 100)
                    chartCard(title: "Mémoire (%)", data: monitor.memHistory, color: AuraTheme.cool, maxY: 100)
                }

                HStack(alignment: .top, spacing: 14) {
                    networkCard
                    memoryDetail
                }

                HStack(alignment: .top, spacing: 14) {
                    coresCard
                    temperaturesCard.frame(width: 360)
                }
                processesCard
            }
            .padding(28)
        }
        .confirmationDialog("Quitter \(processToKill?.name ?? "") ?", isPresented: Binding(
            get: { processToKill != nil }, set: { if !$0 { processToKill = nil } })) {
            Button("Quitter") { if let p = processToKill { monitor.terminate(p.pid) } }
            Button("Forcer à quitter", role: .destructive) { if let p = processToKill { monitor.terminate(p.pid, force: true) } }
        } message: {
            Text("Les modifications non enregistrées de ce processus peuvent être perdues.")
        }
    }

    private func gaugeCard(_ title: String, _ v: Double, _ label: String, _ caption: String) -> some View {
        GlassCard(style: .well) {
            VStack(spacing: 10) {
                RingGauge(value: v, label: label, color: AuraTheme.loadColor(v), size: 96, lineWidth: 10)
                Text(title).fontWeight(.semibold)
                Text(caption).font(.auraCaption).foregroundStyle(.secondary).lineLimit(1)
            }
            .frame(maxWidth: .infinity)
        }
    }

    private var batteryCard: some View {
        let b = monitor.battery
        return GlassCard(style: .well) {
            VStack(spacing: 10) {
                if b.present {
                    RingGauge(value: b.level, label: Fmt.percent(b.level),
                              color: b.level > 0.2 ? AuraTheme.green : AuraTheme.red, size: 96, lineWidth: 10)
                    Text(b.isCharging ? "En charge" : b.onAC ? "Sur secteur" : "Sur batterie").fontWeight(.semibold)
                    HStack(spacing: 8) {
                        if let c = b.cycleCount { Text("\(c) cycles") }
                        if let h = b.health { Text("santé \(Fmt.percent(h))") }
                    }
                    .font(.auraCaption).foregroundStyle(.secondary)
                } else {
                    RingGauge(value: thermalValue, label: thermalLabel, color: thermalColor, size: 96, lineWidth: 10)
                    Text("Thermique").fontWeight(.semibold)
                    Text("Mac de bureau").font(.auraCaption).foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity)
        }
    }

    private var thermalValue: Double {
        switch monitor.thermal {
        case .nominal: return 0.25
        case .fair: return 0.5
        case .serious: return 0.8
        default: return 1
        }
    }
    private var thermalLabel: String {
        switch monitor.thermal {
        case .nominal: return "OK"
        case .fair: return "Tiède"
        case .serious: return "Chaud"
        default: return "Critique"
        }
    }
    private var thermalColor: Color {
        switch monitor.thermal {
        case .nominal: return AuraTheme.green
        case .fair: return AuraTheme.amber
        case .serious: return AuraTheme.amber
        default: return AuraTheme.red
        }
    }

    private func chartCard(title: String, data: [Sample], color: Color, maxY: Double) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Text(title).fontWeight(.semibold)
                Chart(data) { s in
                    AreaMark(x: .value("t", s.t), y: .value("v", s.value))
                        .foregroundStyle(LinearGradient(colors: [color.opacity(0.5), color.opacity(0.02)],
                                                        startPoint: .top, endPoint: .bottom))
                        .interpolationMethod(.catmullRom)
                    LineMark(x: .value("t", s.t), y: .value("v", s.value))
                        .foregroundStyle(color)
                        .interpolationMethod(.catmullRom)
                }
                .chartYScale(domain: 0...maxY)
                .chartXAxis(.hidden)
                .frame(height: 140)
            }
        }
    }

    private var networkCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Réseau").fontWeight(.semibold)
                    Spacer()
                    Label(Fmt.rate(monitor.netIn), systemImage: "arrow.down").foregroundStyle(AuraTheme.cool).font(.auraCaption)
                    Label(Fmt.rate(monitor.netOut), systemImage: "arrow.up").foregroundStyle(AuraTheme.signal).font(.auraCaption)
                }
                Chart {
                    ForEach(monitor.netInHistory) { s in
                        LineMark(x: .value("t", s.t), y: .value("o/s", s.value), series: .value("sens", "Réception"))
                            .foregroundStyle(AuraTheme.cool)
                    }
                    ForEach(monitor.netOutHistory) { s in
                        LineMark(x: .value("t", s.t), y: .value("o/s", s.value), series: .value("sens", "Envoi"))
                            .foregroundStyle(AuraTheme.signal)
                    }
                }
                .chartXAxis(.hidden)
                .chartYAxis {
                    AxisMarks { v in
                        AxisGridLine()
                        AxisValueLabel { if let d = v.as(Double.self) { Text(Fmt.bytes(Int64(d))) } }
                    }
                }
                .frame(height: 140)
            }
        }
    }

    private var memoryDetail: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Répartition mémoire").fontWeight(.semibold)
                    Spacer()
                    Button("Libérer la RAM") { monitor.purgeMemory() }.controlSize(.small)
                    Button("Vider le cache DNS") { monitor.flushDNS() }.controlSize(.small)
                }
                memRow("Applications", monitor.memApp, AuraTheme.cool)
                memRow("Mémoire résidente", monitor.memWired, AuraTheme.signal)
                memRow("Compressée", monitor.memCompressed, AuraTheme.amber)
                memRow("Fichiers en cache", monitor.memCached, AuraTheme.legendDim)
                memRow("Swap utilisé", monitor.swapUsed, AuraTheme.red)
            }
        }
    }

    private func memRow(_ label: String, _ value: Int64, _ color: Color) -> some View {
        HStack {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label).font(.auraCallout)
            Spacer()
            Text(Fmt.bytes(value)).font(.auraCallout.monospacedDigit()).foregroundStyle(.secondary)
        }
        .overlay(alignment: .bottom) {
            GeometryReader { g in
                Capsule().fill(color.opacity(0.35))
                    .frame(width: g.size.width * min(1, Double(value) / Double(max(1, monitor.memTotal))), height: 2)
            }
            .frame(height: 2)
            .offset(y: 5)
        }
    }

    private var coresCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Text("Charge par cœur").fontWeight(.semibold)
                HStack(alignment: .bottom, spacing: 6) {
                    ForEach(Array(monitor.cpuPerCore.enumerated()), id: \.offset) { pair in
                        VStack(spacing: 4) {
                            ZStack(alignment: .bottom) {
                                RoundedRectangle(cornerRadius: 4).fill(.white.opacity(0.06))
                                RoundedRectangle(cornerRadius: 4).fill(AuraTheme.loadColor(pair.element).gradient)
                                    .frame(height: max(2, 80 * pair.element))
                                    .animation(.easeOut(duration: 0.5), value: pair.element)
                            }
                            .frame(height: 80)
                            Text("\(pair.offset + 1)").font(.auraCaption2).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }

    private var temperaturesCard: some View {
        let t = monitor.temps
        return GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Text("Températures").fontWeight(.semibold)
                if t.all.isEmpty {
                    Text("Capteurs non disponibles sur ce Mac.").font(.auraCaption).foregroundStyle(.secondary)
                } else {
                    HStack(spacing: 16) {
                        tempGauge("CPU", t.cpu)
                        tempGauge("GPU", t.gpu)
                        tempGauge("SSD", t.ssd)
                        tempGauge("Batterie", t.battery)
                    }
                    DisclosureGroup("\(t.all.count) capteurs") {
                        ForEach(t.all.prefix(30)) { r in
                            HStack {
                                Text(r.name).font(.auraCaption).lineLimit(1)
                                Spacer()
                                Text(String(format: "%.0f °C", r.celsius)).font(.auraCaption.monospacedDigit())
                                    .foregroundStyle(tempColor(r.celsius))
                            }
                        }
                    }
                    .font(.auraCaption)
                }
            }
        }
    }

    private func tempColor(_ c: Double) -> Color { c < 60 ? AuraTheme.green : c < 85 ? AuraTheme.amber : AuraTheme.red }

    @ViewBuilder
    private func tempGauge(_ label: String, _ value: Double?) -> some View {
        if let v = value {
            RingGauge(value: min(1, v / 110), label: String(format: "%.0f°", v), caption: label,
                      color: tempColor(v), size: 64, lineWidth: 7)
        }
    }

    private var sortedProcesses: [ProcessInfoRow] {
        let base = search.isEmpty ? monitor.processes
            : monitor.processes.filter { $0.name.localizedCaseInsensitiveContains(search) }
        return Array(base.sorted { sortByMemory ? $0.memory > $1.memory : $0.cpu > $1.cpu }.prefix(25))
    }

    private var processesCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Processus les plus gourmands").fontWeight(.semibold)
                    Spacer()
                    TextField("Rechercher", text: $search).textFieldStyle(.roundedBorder).frame(width: 180)
                    Picker("", selection: $sortByMemory) {
                        Text("Processeur").tag(false)
                        Text("Mémoire").tag(true)
                    }
                    .pickerStyle(.segmented).frame(width: 200)
                }
                ForEach(sortedProcesses) { p in
                    HStack {
                        Text(p.name).lineLimit(1)
                        Spacer()
                        Text(String(format: "%.1f %%", p.cpu)).monospacedDigit().frame(width: 70, alignment: .trailing)
                            .foregroundStyle(p.cpu > 50 ? AuraTheme.amber : .secondary)
                        Text(Fmt.bytes(p.memory)).monospacedDigit().frame(width: 90, alignment: .trailing)
                            .foregroundStyle(.secondary)
                        Button { processToKill = p } label: { Image(systemName: "xmark.circle") }
                            .buttonStyle(.borderless).help("Quitter ce processus")
                    }
                    .font(.auraCallout)
                    Divider().opacity(0.15)
                }
            }
        }
    }
}
