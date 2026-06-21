import SwiftUI

struct FavoritesView: View {
    @EnvironmentObject private var store: LibraryStore

    var body: some View {
        NavigationStack {
            Group {
                if store.favorites.isEmpty {
                    ContentUnavailableView(
                        "还没有收藏",
                        systemImage: "bookmark",
                        description: Text("打开视频详情，点右上角书签。")
                    )
                } else {
                    List(store.favorites) { video in
                        NavigationLink(value: video) {
                            VideoRow(video: video)
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("收藏")
            .navigationDestination(for: VideoRecord.self) { video in
                VideoDetailView(video: video)
            }
        }
    }
}
