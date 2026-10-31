import SwiftUI
import AppKit

/// Algorithme « squarified treemap » : des rectangles aussi carrés que possible.
enum Treemap {
    static func layout(_ values: [Double], in rect: CGRect) -> [CGRect] {
        let total = values.reduce(0, +)
        guard total > 0, rect.width > 0, rect.height > 0 else { return values.map { _ in .zero } }
        let scale = Double(rect.width * rect.height) / total
        let items = values.map { $0 * scale }
        var result: [CGRect] = []
        var remaining = rect
        var i = 0
        while i < items.count {
            let side = Double(min(remaining.width, remaining.height))
            var row = [items[i]]
            var j = i + 1
            while j < items.count, worst(row + [items[j]], side) <= worst(row, side) {
                row.append(items[j]); j += 1
            }
            let sum = row.reduce(0, +)
            if remaining.width >= remaining.height {
                let w = CGFloat(sum / Double(remaining.height))
                var y = remaining.minY
                for v in row {
                    let h = CGFloat(v) / max(w, 0.0001)
                    result.append(CGRect(x: remaining.minX, y: y, width: w, height: h)); y += h
                }
                remaining = CGRect(x: remaining.minX + w, y: remaining.minY,
                                   width: max(0, remaining.width - w), height: remaining.height)
            } else {
                let h = CGFloat(sum / Double(remaining.width))
                var x = remaining.minX
                for v in row {
                    let w = CGFloat(v) / max(h, 0.0001)
                    result.append(CGRect(x: x, y: remaining.minY, width: w, height: h)); x += w
                }
                remaining = CGRect(x: remaining.minX, y: remaining.minY + h,
                                   width: remaining.width, height: max(0, remaining.height - h))
            }
            i = j
        }
        return result
    }

    private static func worst(_ row: [Double], _ side: Double) -> Double {
        let s = row.reduce(0, +)
        guard let mx = row.max(), let mn = row.min(), s > 0, mn > 0, side > 0 else { return .infinity }
        return max(side * side * mx / (s * s), (s * s) / (side * side * mn))
    }
}

struct SpaceMapView: View {
    @EnvironmentObject var tools: FileTools
    @EnvironmentObject var router: Router
    @Etat private var history: [URL] = []
    @Etat private var hovered: UUID? = nil

    private let palette: [Color] = AuraTheme.categorical

    private var visible: [SpaceNode] { Array(tools.spaceNodes.prefix(60)) }

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .spaceMap, subtitle: "Visualise ce qui occupe ton disque. Clique un dossier pour y entrer.")
            HStack(spacing: 10) {
                Button { goBack() } label: { Image(systemName: "chevron.left") }.disabled(history.isEmpty)
                Button { if let u = pickFolder(start: tools.spaceRoot) { navigate(u, push: true) } } label: {
                    Label(tools.spaceRoot.path.replacingOccurrences(of: FS.home.path, with: "~"), systemImage: "folder")
                        .lineLimit(1).truncationMode(.head)
                }
                Spacer()
                if tools.isBusy { ProgressView().controlSize(.small) }
                Text(tools.status).foregroundStyle(.secondary)
                Button("Mon dossier") { navigate(FS.home, push: true) }
                Button("Disque entier") { navigate(URL(fileURLWithPath: "/"), push: true) }
            }

            HStack(alignment: .top, spacing: 14) {
                GlassCard(padding: 8) {
                    GeometryReader { geo in
                        let rects = Treemap.layout(visible.map { Double($0.size) },
                                                   in: CGRect(origin: .zero, size: geo.size))
                        ZStack(alignment: .topLeading) {
                            ForEach(Array(visible.enumerated()), id: \.element.id) { pair in
                                tile(pair.element, rect: rects[pair.offset], color: palette[pair.offset % palette.count])
                            }
                        }
                    }
                    .frame(minHeight: 420)
                }
                list.frame(width: 320)
            }
        }
        .padding(28)
        .task {
            if let r = router.consumeRoots().first { navigate(r, push: true) }
            else if tools.spaceNodes.isEmpty && !tools.isBusy { await tools.mapSpace(FS.home) }
        }
    }

    private func tile(_ node: SpaceNode, rect: CGRect, color: Color) -> some View {
        let isHover = hovered == node.id
        return RoundedRectangle(cornerRadius: 6, style: .continuous)
            .fill(color.opacity(isHover ? 0.85 : 0.55).gradient)
            .overlay(alignment: .topLeading) {
                if rect.width > 70 && rect.height > 34 {
                    VStack(alignment: .leading, spacing: 1) {
                        Text(node.name).font(.auraCaption.weight(.semibold)).lineLimit(1)
                        Text(Fmt.bytes(node.size)).font(.auraCaption2).opacity(0.8)
                    }
                    .padding(6).foregroundStyle(.white)
                }
            }
            .frame(width: max(0, rect.width - 3), height: max(0, rect.height - 3))
            .offset(x: rect.minX, y: rect.minY)
            .onHover { hovered = $0 ? node.id : (hovered == node.id ? nil : hovered) }
            .onTapGesture { if node.isDirectory { navigate(node.url, push: true) } else { FS.reveal(node.url) } }
            .help("\(node.name) — \(Fmt.bytes(node.size))")
            .animation(.easeOut(duration: 0.15), value: isHover)
    }

    private var list: some View {
        GlassCard(padding: 10) {
            ScrollView {
                LazyVStack(spacing: 2) {
                    ForEach(Array(tools.spaceNodes.enumerated()), id: \.element.id) { pair in
                        let n = pair.element
                        HStack(spacing: 8) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(pair.offset < 60 ? palette[pair.offset % palette.count] : AuraTheme.hairline)
                                .frame(width: 10, height: 10)
                            Image(systemName: n.isDirectory ? "folder.fill" : "doc.fill").foregroundStyle(.secondary)
                            Text(n.name).lineLimit(1).truncationMode(.middle)
                            Spacer()
                            Text(Fmt.bytes(n.size)).font(.auraCaption.monospacedDigit()).foregroundStyle(.secondary)
                        }
                        .padding(6)
                        .background(hovered == n.id ? Color.white.opacity(0.08) : .clear, in: RoundedRectangle(cornerRadius: 6))
                        .contentShape(Rectangle())
                        .onTapGesture { if n.isDirectory { navigate(n.url, push: true) } }
                        .contextMenu {
                            Button("Afficher dans le Finder") { FS.reveal(n.url) }
                            Button("Envoyer à la Corbeille", role: .destructive) {
                                if FS.trash(n.url) { Task { await tools.mapSpace(tools.spaceRoot) } }
                            }
                        }
                    }
                }
            }
        }
    }

    private func navigate(_ url: URL, push: Bool) {
        if push { history.append(tools.spaceRoot) }
        Task { await tools.mapSpace(url) }
    }

    private func goBack() {
        guard let prev = history.popLast() else { return }
        Task { await tools.mapSpace(prev) }
    }
}
