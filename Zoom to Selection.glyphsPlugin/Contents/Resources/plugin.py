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
            "zh-Hant": "縮放至選取範圍",
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

            # 讀取更新後的 selectedLayerOrigin
            origin = tab.selectedLayerOrigin

            # 計算選取中心在 view coordinates 的位置
            centerViewX = origin.x + (self._zoomCenterX * self._zoomScale)
            centerViewY = origin.y + (self._zoomCenterY * self._zoomScale)

            # 設定 viewPort
            tab.viewPort = NSMakeRect(
                centerViewX - viewPort.size.width / 2,
                centerViewY - viewPort.size.height / 2,
                viewPort.size.width,
                viewPort.size.height
            )

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

        layer = tab.activeLayer()
        if not layer:
            return False

        # 檢查是否真的有選取內容
        # layer.selection 返回選取的節點/元件列表
        # 無選取(沒選任何東西) → 禁用
        # 零尺寸選取(選取一個點) → 啟用
        if not layer.selection or len(layer.selection) == 0:
            return False

        return True