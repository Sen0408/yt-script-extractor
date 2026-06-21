import SwiftUI

struct VideoDetailView: View {
    enum Section: String, CaseIterable, Identifiable {
        case summary = "概览"
        case keyPoints = "要点"
        case deepDive = "深度"
        case comments = "AI 评论"
        case transcript = "字幕"

        var id: String { rawValue }
    }

    @EnvironmentObject private var store: LibraryStore
    @Environment(\.openURL) private var openURL
    @State private var section: Section = .summary
    let video: VideoRecord

    private var current: VideoRecord {
        store.videos.first(where: { $0.id == video.id }) ?? video
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 18) {
                AsyncImage(url: current.thumbnailURL) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().scaledToFill()
                    default:
                        Rectangle().fill(Color.secondary.opacity(0.12))
                    }
                }
                .frame(maxWidth: .infinity)
                .aspectRatio(16 / 9, contentMode: .fit)
                .clipped()

                VStack(alignment: .leading, spacing: 12) {
                    Text(current.title)
                        .font(.title2.weight(.bold))

                    HStack(spacing: 14) {
                        Label(current.minutesLabel, systemImage: "clock")
                        Label("\(current.wordCount) 字", systemImage: "text.word.spacing")
                        Text(current.language)
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)

                    if !current.topics.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 6) {
                                ForEach(current.topics, id: \.self) { topic in
                                    Text(topic)
                                        .font(.caption)
                                        .padding(.horizontal, 9)
                                        .padding(.vertical, 5)
                                        .background(Color.blue.opacity(0.10))
                                        .clipShape(Capsule())
                                }
                            }
                        }
                    }

                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(Section.allCases) { item in
                                Button {
                                    section = item
                                } label: {
                                    Text(item.rawValue)
                                        .font(.subheadline.weight(section == item ? .semibold : .regular))
                                        .foregroundStyle(section == item ? Color.white : Color.primary)
                                        .padding(.horizontal, 12)
                                        .frame(height: 34)
                                        .background(section == item ? Color.red : Color.secondary.opacity(0.10))
                                        .clipShape(Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    content
                }
                .padding(.horizontal)
                .padding(.bottom, 32)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button {
                    Task { await store.toggleFavorite(current) }
                } label: {
                    Image(systemName: current.isFavorite ? "bookmark.fill" : "bookmark")
                }
                .accessibilityLabel(current.isFavorite ? "取消收藏" : "收藏")

                Menu {
                    if let url = current.youtubeURL {
                        Button("在 YouTube 打开", systemImage: "play.rectangle") {
                            openURL(url)
                        }
                    }
                    if let url = current.notionURL {
                        Button("在 Notion 打开", systemImage: "doc.text") {
                            openURL(url)
                        }
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .task { await store.markRead(current) }
    }

    @ViewBuilder
    private var content: some View {
        switch section {
        case .summary:
            ReadingText(value: current.summary)
        case .keyPoints:
            VStack(alignment: .leading, spacing: 14) {
                ForEach(Array(current.keyPoints.enumerated()), id: \.offset) { index, point in
                    HStack(alignment: .top, spacing: 10) {
                        Text("\(index + 1)")
                            .font(.caption.bold())
                            .foregroundStyle(.white)
                            .frame(width: 24, height: 24)
                            .background(Color.red)
                            .clipShape(Circle())
                        Text(point)
                            .font(.body)
                            .textSelection(.enabled)
                    }
                }
            }
        case .deepDive:
            ReadingText(value: current.deepDive)
        case .comments:
            ReadingText(value: current.aiComments)
        case .transcript:
            ReadingText(value: current.transcript, monospaced: true)
        }
    }
}

private struct ReadingText: View {
    let value: String
    var monospaced = false

    var body: some View {
        Text(value.isEmpty ? "暂无内容" : value)
            .font(monospaced ? .system(.callout, design: .monospaced) : .body)
            .lineSpacing(6)
            .textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}
