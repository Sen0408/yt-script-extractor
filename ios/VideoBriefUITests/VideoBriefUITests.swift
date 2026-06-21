import XCTest

final class VideoBriefUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testLibraryOpensVideoDetail() throws {
        let app = XCUIApplication()
        app.launch()

        XCTAssertTrue(
            app.navigationBars["视频解说"].waitForExistence(timeout: 10),
            "视频库首页未出现"
        )

        let firstCell = app.cells.element(boundBy: 0)
        XCTAssertTrue(firstCell.waitForExistence(timeout: 10), "视频库没有加载历史视频")
        firstCell.tap()

        XCTAssertTrue(app.buttons["概览"].waitForExistence(timeout: 5), "详情页缺少概览")
        XCTAssertTrue(app.buttons["要点"].exists, "详情页缺少要点")
        XCTAssertTrue(app.buttons["字幕"].exists, "详情页缺少字幕")
        XCTAssertTrue(app.buttons["收藏"].exists, "详情页缺少收藏功能")
    }
}
