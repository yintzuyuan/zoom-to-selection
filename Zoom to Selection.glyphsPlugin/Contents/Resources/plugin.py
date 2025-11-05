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
        if not bounds:
            return False

        # 檢查是否有異常大的值（> 1e10）或負數尺寸
        if (abs(bounds.origin.x) > 1e10 or
            abs(bounds.origin.y) > 1e10 or
            bounds.size.width < 0 or
            bounds.size.height < 0):
            return False

        return True

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
        """計算文字選取範圍的邊界（Text Tool 模式）"""
        print("\n=== 開始計算文字選取邊界 ===")

        # 使用 selectedLayers 屬性（不是方法）自動處理字符→字形映射
        try:
            selected_layers = tab.selectedLayers  # 注意：這是屬性，不是方法
            print("📍 使用 tab.selectedLayers 屬性")
            print(f"   返回 {len(selected_layers) if selected_layers else 0} 個圖層")

            if not selected_layers or len(selected_layers) == 0:
                print("❌ selectedLayers 返回空列表")
                return None

            # 顯示選取的圖層資訊
            for idx, layer in enumerate(selected_layers[:5]):  # 只顯示前5個
                layer_name = getattr(layer.parent, 'name', 'N/A') if hasattr(layer, 'parent') else 'N/A'
                bounds = layer.bounds
                print(f"   [{idx}] 字形={layer_name}, bounds={bounds}")

        except Exception as e:
            print(f"❌ selectedLayers 失敗: {e}")
            import traceback
            print(traceback.format_exc())
            return None

        # 使用累積寬度計算實際排版邊界
        print(f"\n📏 開始合併邊界（使用累積寬度）:")
        x_offset = 0  # 累積的 X 偏移（文字排版位置）
        min_x = None
        max_x = None
        min_y = None
        max_y = None

        for i, layer in enumerate(selected_layers):
            bounds = layer.bounds
            layer_width = layer.width

            print(f"   圖層 {i}: width={layer_width:.1f}, x_offset={x_offset:.1f}")

            if not bounds or not self._isValidBounds(bounds):
                print(f"      ⚠️  沒有有效 bounds，跳過但計入 width")
                x_offset += layer_width
                continue

            # 計算當前圖層在排版中的實際 X 位置
            # bounds.origin.x 是相對於圖層原點的偏移
            layer_min_x = x_offset + bounds.origin.x
            layer_max_x = x_offset + bounds.origin.x + bounds.size.width
            layer_min_y = bounds.origin.y
            layer_max_y = bounds.origin.y + bounds.size.height

            print(f"      實際 x=[{layer_min_x:.1f}, {layer_max_x:.1f}], y=[{layer_min_y:.1f}, {layer_max_y:.1f}]")

            # 更新總邊界
            if min_x is None:
                min_x = layer_min_x
                max_x = layer_max_x
                min_y = layer_min_y
                max_y = layer_max_y
                print(f"      → 初始化邊界")
            else:
                old_min_x, old_max_x = min_x, max_x
                min_x = min(min_x, layer_min_x)
                max_x = max(max_x, layer_max_x)
                min_y = min(min_y, layer_min_y)
                max_y = max(max_y, layer_max_y)
                if min_x != old_min_x or max_x != old_max_x:
                    print(f"      → 更新邊界: x=[{min_x:.1f}, {max_x:.1f}]")

            # 更新累積偏移
            x_offset += layer_width

        if min_x is None:
            print("❌ 沒有有效的圖層邊界")
            return None

        result = NSMakeRect(min_x, min_y, max_x - min_x, max_y - min_y)
        print(f"\n✅ 最終合併邊界:")
        print(f"   origin=({min_x:.1f}, {min_y:.1f})")
        print(f"   size=({max_x - min_x:.1f}, {max_y - min_y:.1f})")
        print(f"   總寬度（累積）={x_offset:.1f}")
        print("=== 計算完成 ===\n")

        return result

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
            bounds = self._calculateTextSelectionBounds(tab)
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

            # 計算選取中心在 view coordinates 的位置
            # 統一的座標轉換公式（兩種模式都適用）
            centerViewX = origin.x + (self._zoomCenterX * self._zoomScale)
            centerViewY = origin.y + (self._zoomCenterY * self._zoomScale)

            print(f"   view 座標中心=({centerViewX:.1f}, {centerViewY:.1f})")

            # 設定 viewPort
            tab.viewPort = NSMakeRect(
                centerViewX - viewPort.size.width / 2,
                centerViewY - viewPort.size.height / 2,
                viewPort.size.width,
                viewPort.size.height
            )

            print(f"✅ viewPort 已設定: x={centerViewX - viewPort.size.width / 2:.1f}, y={centerViewY - viewPort.size.height / 2:.1f}\n")

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