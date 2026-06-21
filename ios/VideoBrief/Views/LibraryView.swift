import SwiftUI

struct LibraryView: View {
    @EnvironmentObject private var store: LibraryStore
    @State private var searchText = ""
    @State private var showAddVideo = false

    private var filtered: [VideoRecord] {
        guard !searchText.isEmpty else { return store.videos }
        return store.videos.filter { video in
            video.title.localizedCaseInsensitiveContains(searchText)
                || video.summary.localizedCaseInsensitiveContains(searchText)
                || video.topics.contains {
                    $0.localizedCaseInsensitiveContains(searchText)
                }
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                if filtered.isEmpty {
                    ContentUnavailableView(
                        store.videos.isEmpty ? "还没有视频" : "没有搜索结果",
                        systemImage: "play.rectangle",
                        description: Text(
                            store.videos.isEmpty
                                ? "点右上角添加 YouTube 链接。"
                                : "换一个关键词试试。"
                        )
                    )
                } else {
                    List(filtered) { video in
                        NavigationLink(value: video) {
                            VideoRow(video: video)
                        }
                    }
                    .listStyle(.plain)
                    .refreshable { await store.refresh() }
                }
            }
            .navigationTitle("视频解说")
            .searchable(text: $searchText, prompt: "搜索标题、内容或话题")
            .navigationDestination(for: VideoRecord.self) { video in
                VideoDetailView(video: video)
            }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Image(systemName: store.isOnline ? "checkmark.icloud.fill" : "icloud.slash.fill")
                        .foregroundStyle(store.isOnline ? Color.green : Color.orange)
                        .accessibilityLabel(store.isOnline ? "已同步" : "离线缓存")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showAddVideo = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("添加视频")
                }
            }
            .overlay {
                if store.isRefreshing && store.videos.isEmpty {
                    ProgressView("正在同步视频库…")
                }
            }
            .sheet(isPresented: $showAddVideo) {
                AddVideoView()
            }
        }
    }
}
