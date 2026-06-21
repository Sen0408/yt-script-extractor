import SwiftUI
import UIKit

struct SettingsView: View {
    @EnvironmentObject private var store: LibraryStore
    @AppStorage(ServerConfiguration.storageKey)
    private var serverURL = ServerConfiguration.defaultURL
    @State private var testing = false
    @State private var connectionResult: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("http://192.168.x.x:8765", text: $serverURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()

                    Button {
                        testing = true
                        connectionResult = nil
                        Task {
                            let ok = await store.testConnection()
                            connectionResult = ok ? "连接成功" : "连接失败"
                            testing = false
                        }
                    } label: {
                        Label(
                            testing ? "正在测试…" : "测试连接",
                            systemImage: "network"
                        )
                    }
                    .disabled(testing)

                    if let connectionResult {
                        Text(connectionResult)
                            .foregroundStyle(store.isOnline ? .green : .red)
                    }

                    Button("打开系统网络权限", systemImage: "gear") {
                        guard let url = URL(
                            string: UIApplication.openSettingsURLString
                        ) else {
                            return
                        }
                        UIApplication.shared.open(url)
                    }
                } header: {
                    Text("同步服务器")
                } footer: {
                    Text("App 会自动发现 Mac 的安全 HTTPS 入口，在 Wi-Fi、5G 或异地网络均可连接。")
                }

                Section("本地缓存") {
                    LabeledContent("已缓存视频", value: "\(store.videos.count)")
                    LabeledContent(
                        "状态",
                        value: store.isOnline ? "在线同步" : "离线可读"
                    )

                    Button("立即同步", systemImage: "arrow.clockwise") {
                        Task { await store.refresh() }
                    }
                }

                Section("处理流程") {
                    Label("字幕保存在 Mac 与 App 缓存", systemImage: "internaldrive")
                    Label("分析同步到 Notion", systemImage: "doc.text")
                    Label("API 通过私有令牌保护", systemImage: "lock")
                }
            }
            .navigationTitle("设置")
        }
    }
}
