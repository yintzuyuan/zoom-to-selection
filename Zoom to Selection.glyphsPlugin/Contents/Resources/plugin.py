# encoding: utf-8

###########################################################################################################
#
#
# General Plugin
#
# Read the docs:
# https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/General%20Plugin
#
#
###########################################################################################################

# Zoom to Selection
# =================
#
# A plugin to zoom the Edit View to fit the current selection.
# Keyboard Shortcut: Shift+Cmd+0

import objc
from AppKit import (
    NSEventModifierFlagCommand,
    NSEventModifierFlagShift,
    NSMenuItem,
)
from Foundation import NSMakeRect
from GlyphsApp import Glyphs, VIEW_MENU
from GlyphsApp.plugins import GeneralPlugin


class ZoomToSelection(GeneralPlugin):
    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({
            "en": "Zoom to Selection",
            "zh-Hant": "拉至選取範圍",
            "zh-Hans": "缩放至所选项",
            "ja": "選択範囲にズーム",
        })

    @objc.python_method
    def start(self):
        # 建立選單項目
        zoomToSelectionMenuItem = ZoomToSelectionMenuItem.new()
        zoomToSelectionMenuItem.setTitle_(self.name)
        zoomToSelectionMenuItem.setTarget_(self)
        zoomToSelectionMenuItem.setAction_(self.zoomToSelection_)
        
        # 設定快捷鍵：Shift+Cmd+0
        zoomToSelectionMenuItem.setKeyEquivalent_("0")
        zoomToSelectionMenuItem.setKeyEquivalentModifierMask_(
            NSEventModifierFlagShift | NSEventModifierFlagCommand
        )
        
        # 插入到 VIEW 選單的第五個位置（index 4）
        viewMenuItem = Glyphs.menu[VIEW_MENU]
        viewMenu = viewMenuItem.submenu()
        viewMenu.insertItem_atIndex_(zoomToSelectionMenuItem, 4)

    def zoomToSelection_(self, sender):
        """縮放視圖以適應選取範圍"""
        try:
            # 第一階段：設定 scale 和儲存必要資訊
            success = self._setScale()
            if not success:
                return

            # 第二階段：延遲設定 viewPort
            # 使用 performSelector 延遲執行，讓 selectedLayerOrigin 有時間更新
            self.performSelector_withObject_afterDelay_(
                "setViewPortDelayed:",
                None,
                0.01  # 延遲 10ms
            )

        except Exception as e:
            print(f"Zoom to Selection Error: {e}")
            import traceback
            print(traceback.format_exc())

    @objc.python_method
    def _isValidBounds(self, bounds):
        """檢查邊界是否有效（排除異常值）"""
        # 檢查是否為 None 或 callable（換行符號的 bounds 是方法）
        if not bounds or callable(bounds):
            return False

        # 檢查是否有異常大的值（> 1e10）或負數尺寸
        if (abs(bounds.origin.x) > 1e10 or
            abs(bounds.origin.y) > 1e10 or
            bounds.size.width < 0 or
            bounds.size.height < 0):
            return False

        return True

    @objc.python_method
    def _calculateSingleLineBounds(self, selected_layers):
        """計算單行選取的邊界

        Args:
            selected_layers: 選取的 layers

        Returns:
            NSRect: 選取範圍的邊界
        """
        # 收集有效的 bounds 並計算選取寬度
        valid_bounds = []
        selection_width = 0

        for layer in selected_layers:
            bounds = layer.bounds

            # 跳過換行符號
            if callable(bounds):
                continue

            if bounds and self._isValidBounds(bounds):
                valid_bounds.append(bounds)
                selection_width += layer.width

        if not valid_bounds:
            return None

        # 計算 X 範圍：使用第一個字符的 bounds.origin.x（相對座標）
        min_x = valid_bounds[0].origin.x

        # 計算 Y 範圍
        all_y_coords = []
        for bounds in valid_bounds:
            all_y_coords.append(bounds.origin.y)
            all_y_coords.append(bounds.origin.y + bounds.size.height)

        min_y = min(all_y_coords)
        max_y = max(all_y_coords)
        height = max_y - min_y

        return NSMakeRect(min_x, min_y, selection_width, height)

    @objc.python_method
    def _calculateMultiLineBounds(self, selected_layers, edit_view_width, selection_width):
        """計算跨行選取的邊界

        Args:
            selected_layers: 選取的 layers
            edit_view_width: 編輯器寬度
            selection_width: 選取範圍的總寬度

        Returns:
            NSRect: 選取範圍的邊界
        """
        # 收集有效的 bounds（跳過換行符號）
        valid_bounds = []
        for layer in selected_layers:
            bounds = layer.bounds

            # 跳過換行符號
            if callable(bounds):
                continue

            if bounds and self._isValidBounds(bounds):
                valid_bounds.append(bounds)

        if not valid_bounds:
            return None

        # 獲取第一個字符的 bounds
        first_bounds = valid_bounds[0]

        # 計算第一個字符的中心點（作為起始參考點）
        first_center_y = first_bounds.origin.y + first_bounds.size.height / 2

        # 計算選取字符的實際 Y 範圍（用於計算單行高度）
        all_y_coords = []
        for bounds in valid_bounds:
            all_y_coords.append(bounds.origin.y)
            all_y_coords.append(bounds.origin.y + bounds.size.height)

        actual_min_y = min(all_y_coords)
        actual_max_y = max(all_y_coords)
        single_line_height = actual_max_y - actual_min_y

        # 計算跨越的行數
        import math
        estimated_lines = math.ceil(selection_width / edit_view_width)

        # 計算總高度
        height = single_line_height * estimated_lines

        # 跨行時的中心點計算：
        # X: 使用行首到行尾的中點（editViewWidth 的一半）
        center_x = edit_view_width / 2

        # Y: 從第一個字符中心點開始，往下延伸 (estimated_lines - 1) 行
        #    然後取整體的中點
        # 注意：Glyphs 座標系統 Y 軸向上為正，往下是減
        center_y = first_center_y - (estimated_lines - 1) * single_line_height / 2

        # 跨行時的寬度使用整個編輯器行寬
        width = edit_view_width

        print(f"   選取寬度: {selection_width:.1f}")
        print(f"   編輯器寬度: {edit_view_width:.1f}")
        print(f"   估計行數: {estimated_lines}")
        print(f"   單行高度: {single_line_height:.1f}")
        print(f"   總高度: {height:.1f}")
        print(f"   第一個字符中心Y: {first_center_y:.1f}")
        print(f"   計算偏移: {(estimated_lines - 1) * single_line_height / 2:.1f}")
        print(f"   計算的中心點: ({center_x:.1f}, {center_y:.1f})")

        # 使用中心點計算矩形的起點
        min_x = center_x - width / 2
        min_y = center_y - height / 2

        print(f"   最終矩形: origin=({min_x:.1f}, {min_y:.1f}), size=({width:.1f}, {height:.1f})")

        return NSMakeRect(min_x, min_y, width, height)

    @objc.python_method
    def _calculateSelectionBounds(self, layer):
        """手動計算選取範圍的邊界（支援 GSHandle/extra nodes）"""
        selection = layer.selection
        if not selection or len(selection) == 0:
            return None

        # 收集所有選取項目的座標
        x_coords = []
        y_coords = []

        for item in selection:
            # GSHandle (extra nodes) 使用 .position
            if hasattr(item, 'position'):
                x_coords.append(item.position.x)
                y_coords.append(item.position.y)
            # GSNode 使用 .x 和 .y
            elif hasattr(item, 'x') and hasattr(item, 'y'):
                x_coords.append(item.x)
                y_coords.append(item.y)

        if not x_coords:
            return None

        # 計算邊界框
        min_x = min(x_coords)
        max_x = max(x_coords)
        min_y = min(y_coords)
        max_y = max(y_coords)

        return NSMakeRect(min_x, min_y, max_x - min_x, max_y - min_y)

    @objc.python_method
    def _calculateTextSelectionBounds(self, tab):
        """計算文字選取範圍的邊界（Text Tool 模式）

        Returns:
            tuple: (NSRect 邊界, bool 是否跨行, float 累積寬度)
        """
        print("\n=== 開始計算文字選取邊界 ===")

        # 取得選取的圖層
        try:
            selected_layers = tab.selectedLayers
            edit_view_width = Glyphs.editViewWidth

            print(f"📍 選取圖層數量: {len(selected_layers) if selected_layers else 0}")
            print(f"📍 編輯器寬度: {edit_view_width}")

            if not selected_layers or len(selected_layers) == 0:
                print("❌ 沒有選取任何圖層")
                return None

        except Exception as e:
            print(f"❌ 取得圖層資訊失敗: {e}")
            import traceback
            print(traceback.format_exc())
            return None

        # 計算選取範圍的總寬度並檢測換行符號
        print("\n📏 分析選取範圍:")
        selection_width = 0
        has_newline = False
        valid_layer_count = 0

        for layer in selected_layers:
            if callable(layer.bounds):
                # 換行符號
                has_newline = True
                print("   檢測到換行符號")
            else:
                selection_width += layer.width
                valid_layer_count += 1

        print(f"   有效字符數量: {valid_layer_count}")
        print(f"   選取總寬度: {selection_width:.1f}")
        print(f"   包含換行符號: {has_newline}")

        # 判斷是否跨行
        is_multiline = (selection_width > edit_view_width) or has_newline

        if is_multiline:
            reason = "寬度超過 editViewWidth" if selection_width > edit_view_width else "包含換行符號"
            print(f"   判定: ✓ 跨行選取 ({reason})")
        else:
            print("   判定: ✓ 單行選取")

        # 計算累積寬度（跨行模式需要）
        accumulated_width = 0
        if is_multiline and tab.layers:
            first_selected_index = tab.layersCursor  # 第一個選取字符的索引
            print(f"\n📐 計算累積寬度:")
            print(f"   第一個選取字符索引: {first_selected_index}")
            
            # 計算從索引 0 到第一個選取字符之間的累積寬度
            for i in range(first_selected_index):
                layer = tab.layers[i]
                if not callable(layer.bounds):  # 跳過換行符號
                    accumulated_width += layer.width
            
            print(f"   累積寬度 (索引 0 到 {first_selected_index}): {accumulated_width:.1f}")

        # 計算邊界
        if is_multiline:
            # 跨行模式
            print("\n📐 計算邊界 (跨行模式):")
            result = self._calculateMultiLineBounds(selected_layers, edit_view_width, selection_width)

            if result:
                center_x = result.origin.x + result.size.width / 2
                center_y = result.origin.y + result.size.height / 2
                print(f"   使用寬度: {result.size.width:.1f}")
                print(f"   起始 X: {result.origin.x:.1f}")
                print(f"   中心點 X: {center_x:.1f}")
                print(f"   Y 範圍: {result.origin.y:.1f} ~ {result.origin.y + result.size.height:.1f}")
                print(f"   高度: {result.size.height:.1f}")
                print(f"   中心點 Y: {center_y:.1f}")

            if not result:
                print("❌ 無法計算邊界")
                return None

            print("\n✅ 最終邊界:")
            print(f"   origin=({result.origin.x:.1f}, {result.origin.y:.1f})")
            print(f"   size=({result.size.width:.1f}, {result.size.height:.1f})")
            print("=== 計算完成 ===\n")

            return result, True, accumulated_width
        else:
            # 單行模式
            print("\n📐 計算邊界 (單行模式):")
            result = self._calculateSingleLineBounds(selected_layers)

            if result:
                center_x = result.origin.x + result.size.width / 2
                print(f"   起始 X: {result.origin.x:.1f}")
                print(f"   選取寬度: {result.size.width:.1f}")
                print(f"   中心點 X: {center_x:.1f}")

            if not result:
                print("❌ 無法計算邊界")
                return None

            print("\n✅ 最終邊界:")
            print(f"   origin=({result.origin.x:.1f}, {result.origin.y:.1f})")
            print(f"   size=({result.size.width:.1f}, {result.size.height:.1f})")
            print("=== 計算完成 ===\n")

            return result, False, 0

    @objc.python_method
    def _calculateDynamicPadding(self, selWidth, selHeight):
        """根據選取範圍大小動態計算 PADDING

        選取範圍較大時返回較小的 PADDING（1.5）
        選取範圍較小時返回較大的 PADDING（2.0）
        中間範圍線性漸變
        """
        # 使用較大維度作為判斷依據
        selectionSize = max(selWidth, selHeight)

        # 參數設定
        MIN_PADDING = 1.5  # 大範圍時的邊距
        MAX_PADDING = 3.0  # 小範圍時的邊距
        SMALL_SIZE = 300   # 小範圍臨界值（font units）
        LARGE_SIZE = 800   # 大範圍臨界值（font units）

        if selectionSize <= SMALL_SIZE:
            return MAX_PADDING
        elif selectionSize >= LARGE_SIZE:
            return MIN_PADDING
        else:
            # 線性漸變
            ratio = (selectionSize - SMALL_SIZE) / (LARGE_SIZE - SMALL_SIZE)
            return MAX_PADDING - (MAX_PADDING - MIN_PADDING) * ratio

    @objc.python_method
    def _setScale(self):
        """第一階段：設定 scale 並儲存必要資訊"""
        tab = Glyphs.font.currentTab
        if not tab:
            return False

        # 檢查是否為文字選取模式（Text Tool）
        # 優先檢查，因為在文字模式時 activeLayer 可能為 None
        if hasattr(tab, 'textRange') and tab.textRange > 0:
            bounds_info = self._calculateTextSelectionBounds(tab)
            if bounds_info:
                bounds, is_multiline, accumulated_width = bounds_info
                self._isMultiline = is_multiline
                self._accumulatedWidth = accumulated_width
            else:
                return False
        else:
            # 節點選取模式（Edit Tool）
            layer = tab.activeLayer()
            if not layer:
                return False

            # 嘗試使用官方 API
            bounds = layer.selectionBounds

            # 如果 API 返回無效值（如選取 extra nodes），手動計算
            if not self._isValidBounds(bounds):
                bounds = self._calculateSelectionBounds(layer)

            self._isMultiline = False
            self._accumulatedWidth = 0

        if not bounds:
            return False

        # 取得視口大小
        viewPort = tab.viewPort

        # 處理零尺寸選取
        selWidth = bounds.size.width
        selHeight = bounds.size.height

        # 最小尺寸參數
        MIN_SIZE = 100  # font units

        if selWidth == 0 and selHeight == 0:
            # 單點選取:使用固定縮放和最大 PADDING
            targetSize = MIN_SIZE
            newScale = min(viewPort.size.width, viewPort.size.height) / targetSize

        elif selWidth == 0:
            # 垂直線:基於視口高度計算，使用動態 PADDING
            padding = self._calculateDynamicPadding(0, selHeight)
            targetSize = selHeight * padding
            newScale = viewPort.size.height / targetSize

        elif selHeight == 0:
            # 水平線:基於視口寬度計算，使用動態 PADDING
            padding = self._calculateDynamicPadding(selWidth, 0)
            targetSize = selWidth * padding
            newScale = viewPort.size.width / targetSize

        else:
            # 正常選取:分別計算寬高的 scale，取較小值確保完全可見
            padding = self._calculateDynamicPadding(selWidth, selHeight)
            targetWidth = selWidth * padding
            targetHeight = selHeight * padding
            scaleX = viewPort.size.width / targetWidth
            scaleY = viewPort.size.height / targetHeight
            newScale = min(scaleX, scaleY)

        # 計算選取中心點(font units)
        centerX = bounds.origin.x + selWidth / 2
        centerY = bounds.origin.y + selHeight / 2

        # 儲存資訊供延遲執行使用
        self._zoomCenterX = centerX
        self._zoomCenterY = centerY
        self._zoomScale = newScale

        # 設定 scale
        tab.scale = newScale

        return True

    def setViewPortDelayed_(self, _):
        """第二階段：延遲設定 viewPort（在 selectedLayerOrigin 更新後）"""
        try:
            tab = Glyphs.font.currentTab
            if not tab:
                return

            # 取得視口大小
            viewPort = tab.viewPort

            # 統一使用 selectedLayerOrigin（文字模式和節點模式都適用）
            origin = tab.selectedLayerOrigin

            print("\n📍 設定 viewport 定位")
            print(f"   selectedLayerOrigin=({origin.x:.1f}, {origin.y:.1f})")
            print(f"   選取中心點 (font units)=({self._zoomCenterX:.1f}, {self._zoomCenterY:.1f})")
            print(f"   scale={self._zoomScale:.3f}")

            # 根據模式選擇不同的 X 軸計算方式
            if self._isMultiline:
                # 跨行模式：從行首（索引 0）開始計算
                edit_view_width = Glyphs.editViewWidth
                
                # 步驟 1：反推行首（索引 0）在 view coordinates 的位置
                lineStartViewX = origin.x - (self._accumulatedWidth * self._zoomScale)
                
                # 步驟 2：行中心 = 行首 + 行寬一半
                centerViewX = lineStartViewX + ((edit_view_width / 2) * self._zoomScale)

                print("📍 跨行模式定位")
                print(f"   累積寬度 (索引0到選取起點): {self._accumulatedWidth:.1f}")
                print(f"   → 行首 view X (索引0): {lineStartViewX:.1f}")
                print(f"   → 行中心 view X (索引0 + 行寬/2): {centerViewX:.1f}")
            else:
                # 單行模式：跟隨第一個字符的位置
                centerViewX = origin.x + (self._zoomCenterX * self._zoomScale)

                print("📍 單行模式定位")
                print(f"   selectedLayerOrigin.x: {origin.x:.1f}")
                print(f"   相對中心 (font units): {self._zoomCenterX:.1f}")
                print(f"   view 座標中心 X: {centerViewX:.1f}")

            # Y 軸計算相同
            centerViewY = origin.y + (self._zoomCenterY * self._zoomScale)
            print(f"   view 座標中心 Y: {centerViewY:.1f}")

            # 設定 viewPort
            tab.viewPort = NSMakeRect(
                centerViewX - viewPort.size.width / 2,
                centerViewY - viewPort.size.height / 2,
                viewPort.size.width,
                viewPort.size.height
            )

            print("✅ viewPort 已設定\n")

        except Exception as e:
            print(f"Zoom to Selection (Delayed) Error: {e}")
            import traceback
            print(traceback.format_exc())

    @objc.python_method
    def __file__(self):
        """Please leave this method unchanged"""
        return __file__


class ZoomToSelectionMenuItem(NSMenuItem):
    """自訂選單項目，用於控制啟用狀態"""

    def isEnabled(self):
        """只有在有字型且有選取內容時才啟用"""
        if not Glyphs.font:
            return False

        tab = Glyphs.font.currentTab
        if not tab:
            return False

        # 檢查文字選取（Text Tool 模式）
        # 優先檢查，因為在文字模式時 activeLayer 可能為 None
        if hasattr(tab, 'textRange') and tab.textRange > 0:
            return True

        # 檢查節點選取（Edit Tool 模式）
        layer = tab.activeLayer()
        if not layer:
            return False

        # layer.selection 返回選取的節點/元件列表
        # 無選取(沒選任何東西) → 禁用
        # 零尺寸選取(選取一個點) → 啟用
        if not layer.selection or len(layer.selection) == 0:
            return False

        return True