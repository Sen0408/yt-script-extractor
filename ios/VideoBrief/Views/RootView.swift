import SwiftUI

struct RootView: View {
    @EnvironmentObject private var store: LibraryStore

    var body: some View {
        TabView {
            LibraryView()
                .tabItem {
                    Label("视频库", systemImage: "play.rectangle.on.rectangle")
                }

            FavoritesView()
                .tabItem {
                    Label("收藏", systemImage: "bookmark")
                }

            SettingsView()
                .tabItem {
                    Label("设置", systemImage: "gearshape")
                }
        }
        .alert(
            "发生错误",
            isPresented: Binding(
                get: { store.errorMessage != nil },
                set: { if !$0 { store.errorMessage = nil } }
            )
        ) {
            Button("好", role: .cancel) {}
        } message: {
            Text(store.errorMessage ?? "")
        }
    }
}
