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
        """計算文字選取範圍的邊界（Text Tool 模式）

        改進版：
        1. 使用 Y 座標變化檢測跨行
        2. 跨行時使用 Glyphs.editViewWidth 作為寬度
        3. 單行時嘗試簡化計算（驗證座標性質）
        """
        print("\n=== 開始計算文字選取邊界（改進版）===")

        # 取得選取的圖層
        try:
            selected_layers = tab.selectedLayers
            print("📍 使用 tab.selectedLayers 屬性")
            print(f"   返回 {len(selected_layers) if selected_layers else 0} 個圖層")

            if not selected_layers or len(selected_layers) == 0:
                print("❌ selectedLayers 返回空列表")
                return None

        except Exception as e:
            print(f"❌ selectedLayers 失敗: {e}")
            import traceback
            print(traceback.format_exc())
            return None

        # 收集有效的邊界框
        print("\n📦 收集有效邊界:")
        valid_bounds = []
        for idx, layer in enumerate(selected_layers):
            layer_name = getattr(layer.parent, 'name', 'N/A') if hasattr(layer, 'parent') else 'N/A'
            bounds = layer.bounds

            if bounds and self._isValidBounds(bounds):
                valid_bounds.append({
                    'layer': layer,
                    'bounds': bounds,
                    'index': idx,
                    'name': layer_name
                })
                if idx < 3 or idx >= len(selected_layers) - 2:  # 顯示前3個和後2個
                    print(f"   [{idx}] {layer_name}: bounds.origin=({bounds.origin.x:.1f}, {bounds.origin.y:.1f}), "
                          f"size=({bounds.size.width:.1f}, {bounds.size.height:.1f}), layer.width={layer.width:.1f}")
            elif idx < 3:
                print(f"   [{idx}] {layer_name}: ⚠️ 無效或缺少 bounds")

        if not valid_bounds:
            print("❌ 沒有有效的圖層邊界")
            return None

        if len(valid_bounds) < len(selected_layers):
            print(f"   ⚠️ {len(selected_layers) - len(valid_bounds)} 個圖層沒有有效 bounds")

        # 檢測是否跨行：Y 座標變化檢測
        print("\n🔍 檢測是否跨行:")
        y_coords = [item['bounds'].origin.y for item in valid_bounds]
        min_y = min(y_coords)
        max_y_origin = max(y_coords)
        y_range = max_y_origin - min_y

        # 閾值設定：根據字形高度判斷
        # 取第一個有效邊界的高度作為參考
        first_height = valid_bounds[0]['bounds'].size.height
        y_threshold = max(50, first_height * 0.3)  # 至少 50，或字形高度的 30%

        is_multiline = y_range > y_threshold

        print(f"   Y 座標範圍: {min_y:.1f} ~ {max_y_origin:.1f} (差距={y_range:.1f})")
        print(f"   參考字形高度: {first_height:.1f}, 閾值: {y_threshold:.1f}")
        print(f"   判定: {'✓ 跨行選取' if is_multiline else '✓ 單行選取'}")

        # 計算邊界框
        if is_multiline:
            # === 跨行模式：使用 editViewWidth ===
            print("\n📐 跨行模式計算:")
            edit_view_width = Glyphs.editViewWidth
            print(f"   editViewWidth = {edit_view_width}")

            width = edit_view_width
            min_x = 0  # 假設從行首開始

            # Y 範圍：涵蓋所有字形的完整高度
            all_y_coords = []
            for item in valid_bounds:
                b = item['bounds']
                all_y_coords.append(b.origin.y)
                all_y_coords.append(b.origin.y + b.size.height)

            min_y = min(all_y_coords)
            max_y = max(all_y_coords)
            height = max_y - min_y

            print(f"   使用寬度: {width} (editViewWidth)")
            print(f"   Y 範圍: {min_y:.1f} ~ {max_y:.1f} (高度={height:.1f})")

        else:
            # === 單行模式：嘗試簡化計算 ===
            print("\n📏 單行模式計算:")

            # 方法 1：嘗試直接使用第一個和最後一個的座標
            first_item = valid_bounds[0]
            last_item = valid_bounds[-1]

            first_bounds = first_item['bounds']
            last_bounds = last_item['bounds']

            print(f"   第一個字形: {first_item['name']}")
            print(f"     bounds.origin.x = {first_bounds.origin.x:.1f}")
            print(f"     layer.width = {first_item['layer'].width:.1f}")
            print(f"   最後一個字形: {last_item['name']}")
            print(f"     bounds.origin.x = {last_bounds.origin.x:.1f}")
            print(f"     bounds.size.width = {last_bounds.size.width:.1f}")
            print(f"     layer.width = {last_item['layer'].width:.1f}")

            # 嘗試簡化計算：假設 bounds.origin.x 反映實際位置關係
            simple_min_x = first_bounds.origin.x
            simple_max_x = last_bounds.origin.x + last_bounds.size.width
            simple_width = simple_max_x - simple_min_x

            print(f"   簡化計算: min_x={simple_min_x:.1f}, max_x={simple_max_x:.1f}, width={simple_width:.1f}")

            # 方法 2：累積寬度計算（作為對照）
            accumulated_x = 0
            accum_min_x = None
            accum_max_x = None

            for item in valid_bounds:
                layer = item['layer']
                bounds = item['bounds']

                layer_min_x = accumulated_x + bounds.origin.x
                layer_max_x = accumulated_x + bounds.origin.x + bounds.size.width

                if accum_min_x is None:
                    accum_min_x = layer_min_x
                    accum_max_x = layer_max_x
                else:
                    accum_min_x = min(accum_min_x, layer_min_x)
                    accum_max_x = max(accum_max_x, layer_max_x)

                accumulated_x += layer.width

            accum_width = accum_max_x - accum_min_x
            print(f"   累積計算: min_x={accum_min_x:.1f}, max_x={accum_max_x:.1f}, width={accum_width:.1f}")

            # 比較兩種方法的差異
            width_diff = abs(simple_width - accum_width)
            print(f"   寬度差異: {width_diff:.1f}")

            # 選擇使用的方法
            if width_diff < 1.0:  # 差異小於 1 單位，視為相同
                print("   → 使用簡化計算（差異可忽略）")
                min_x = simple_min_x
                width = simple_width
            else:
                print("   → 使用累積計算（差異顯著，bounds 可能是相對座標）")
                min_x = accum_min_x
                width = accum_width

            # Y 範圍計算
            all_y_coords = []
            for item in valid_bounds:
                b = item['bounds']
                all_y_coords.append(b.origin.y)
                all_y_coords.append(b.origin.y + b.size.height)

            min_y = min(all_y_coords)
            max_y = max(all_y_coords)
            height = max_y - min_y

        result = NSMakeRect(min_x, min_y, width, height)
        print("\n✅ 最終邊界:")
        print(f"   origin=({min_x:.1f}, {min_y:.1f})")
        print(f"   size=({width:.1f}, {height:.1f})")
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