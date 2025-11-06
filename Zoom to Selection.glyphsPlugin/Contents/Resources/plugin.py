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
    def _collectSelectionInfo(self, selected_layers, tab):
        """統一收集選取範圍的基本資訊

        Args:
            selected_layers: 選取的 layers
            tab: 當前編輯分頁

        Returns:
            dict: 包含以下鍵值的字典
                - valid_layers: 有效的 layer 列表
                - valid_bounds: 有效的 bounds 列表
                - selection_width: 選取總寬度
                - has_newline: 是否包含換行符號
                - line_breaks: 換行符號的位置索引列表
                - first_selected_index: 第一個選取字符的索引
        """
        info = {
            'valid_layers': [],
            'valid_bounds': [],
            'selection_width': 0,
            'has_newline': False,
            'line_breaks': [],
            'first_selected_index': tab.layersCursor if hasattr(tab, 'layersCursor') else 0,
        }

        for idx, layer in enumerate(selected_layers):
            bounds = layer.bounds

            # 檢查是否為換行符號
            if callable(bounds):
                info['has_newline'] = True
                info['line_breaks'].append(idx)
                continue

            # 檢查是否為有效的 bounds
            if bounds and self._isValidBounds(bounds):
                info['valid_layers'].append(layer)
                info['valid_bounds'].append(bounds)
                info['selection_width'] += layer.width

        return info

    @objc.python_method
    def _getLineHeight(self, font, valid_bounds):
        """取得行高

        Args:
            font: 當前字體
            valid_bounds: 有效的 bounds 列表

        Returns:
            float: 行高值
        """
        # 優先使用 EditView Line Height 自訂參數
        line_height_param = font.customParameters['EditView Line Height']
        if line_height_param is not None:
            return float(line_height_param)

        # 如果沒有設定，則使用選取字符的實際高度範圍
        if valid_bounds:
            all_y_coords = []
            for bounds in valid_bounds:
                all_y_coords.append(bounds.origin.y)
                all_y_coords.append(bounds.origin.y + bounds.size.height)

            if all_y_coords:
                return max(all_y_coords) - min(all_y_coords)

        # 預設值：使用 UPM * 1.2
        return font.upm * 1.2

    @objc.python_method
    def _analyzeLineStructure(self, tab, info, edit_view_width):
        """分析選取範圍的行結構（使用行號比較法）

        追蹤從索引 0 到最後一個選取字符，記錄：
        1. 第一個選取字符所在的行號
        2. 最後一個選取字符所在的行號
        3. 第一個選取字符前的累積寬度（僅當前行）

        選取範圍行數 = 最後一個字符行號 - 第一個字符行號 + 1

        Args:
            tab: 當前編輯分頁
            info: 從 _collectSelectionInfo 收集的資訊
            edit_view_width: 編輯器寬度

        Returns:
            dict: {
                'total_lines': int,              # 選取範圍總行數
                'accumulated_width': float,      # 第一個選取字符前的累積寬度（當前行）
                'is_multiline': bool             # 是否跨行
            }
        """
        first_selected_index = info['first_selected_index']
        last_selected_index = first_selected_index + len(info['valid_layers']) - 1

        # 追蹤整個範圍（從索引 0 到最後一個選取字符）
        current_line = 0
        current_line_width = 0.0
        first_selected_line = None
        last_selected_line = None
        accumulated_width_at_first = 0.0

        if hasattr(tab, 'layers') and tab.layers:
            for i in range(last_selected_index + 1):
                layer = tab.layers[i]

                # 遇到換行符號：進入新行
                if callable(layer.bounds):
                    current_line += 1
                    current_line_width = 0.0
                    continue

                # 檢查是否因寬度超過而自動換行
                if current_line_width + layer.width > edit_view_width:
                    current_line += 1
                    current_line_width = layer.width
                else:
                    current_line_width += layer.width

                # 記錄第一個選取字符的位置
                if i == first_selected_index:
                    first_selected_line = current_line
                    accumulated_width_at_first = current_line_width - layer.width

                # 記錄最後一個選取字符的位置
                if i == last_selected_index:
                    last_selected_line = current_line

        # 計算選取範圍跨越的行數
        if first_selected_line is not None and last_selected_line is not None:
            selected_lines = last_selected_line - first_selected_line + 1
        else:
            selected_lines = 1

        # 判斷是否跨行
        is_multiline = (selected_lines > 1)

        print("\n📊 行結構分析 (行號比較法):")
        print(f"   第一個選取字符所在行: {first_selected_line}")
        print(f"   最後一個選取字符所在行: {last_selected_line}")
        print(f"   第一個字符前的累積寬度: {accumulated_width_at_first:.1f}")
        print(f"   選取範圍總行數: {selected_lines}")
        print(f"   是否跨行: {is_multiline}")

        return {
            'total_lines': selected_lines,
            'accumulated_width': accumulated_width_at_first,
            'is_multiline': is_multiline
        }

    @objc.python_method
    def _calculateUnifiedBounds(self, info, edit_view_width, font, tab):
        """統一的邊界計算方法（合併單行和多行邏輯）

        Args:
            info: 從 _collectSelectionInfo 收集的資訊
            edit_view_width: 編輯器寬度
            font: 當前字體
            tab: 當前編輯分頁

        Returns:
            tuple: (NSRect 邊界, bool 是否跨行, float 累積寬度)
        """
        valid_bounds = info['valid_bounds']
        if not valid_bounds:
            return None, False, 0

        # 分析行結構（同時計算跨行判斷、累積寬度、總行數）
        line_info = self._analyzeLineStructure(tab, info, edit_view_width)
        is_multiline = line_info['is_multiline']
        accumulated_width = line_info['accumulated_width']

        # 計算 Y 範圍（單行和多行都需要）
        all_y_coords = []
        for bounds in valid_bounds:
            all_y_coords.append(bounds.origin.y)
            all_y_coords.append(bounds.origin.y + bounds.size.height)

        min_y = min(all_y_coords)
        max_y = max(all_y_coords)

        if is_multiline:
            # === 跨行模式 ===
            # 計算行高
            line_height = self._getLineHeight(font, valid_bounds)

            # 使用行結構分析的結果
            actual_lines = line_info['total_lines']

            # 計算總高度
            height = line_height * actual_lines

            # X 軸：使用完整行寬
            width = edit_view_width
            min_x = 0  # 從行首開始

            # 計算中心點
            # X: 行中心
            center_x = edit_view_width / 2

            # Y: 第一行中心到最後一行中心的中點
            first_bounds = valid_bounds[0]
            first_line_center_y = first_bounds.origin.y + first_bounds.size.height / 2
            last_line_center_y = first_line_center_y - (actual_lines - 1) * line_height
            center_y = (first_line_center_y + last_line_center_y) / 2

            # 使用中心點計算矩形起點
            min_y = center_y - height / 2

            print("\n📐 跨行模式邊界計算:")
            print(f"   選取寬度: {info['selection_width']:.1f}")
            print(f"   編輯器寬度: {edit_view_width:.1f}")
            print(f"   包含換行: {info['has_newline']}")
            print(f"   行數: {actual_lines}")
            print(f"   行高: {line_height:.1f}")
            print(f"   總高度: {height:.1f}")
            print(f"   中心點: ({center_x:.1f}, {center_y:.1f})")
            print(f"   累積寬度: {accumulated_width:.1f}")

        else:
            # === 單行模式 ===
            # 計算選取範圍相對於行首的起始位置
            min_x = valid_bounds[0].origin.x
            width = info['selection_width']
            height = max_y - min_y

            # 中心點
            center_x = min_x + width / 2
            center_y = min_y + height / 2

            print("\n📐 單行模式邊界計算:")
            print(f"   起始 X: {min_x:.1f}")
            print(f"   選取寬度: {width:.1f}")
            print(f"   高度: {height:.1f}")
            print(f"   中心點: ({center_x:.1f}, {center_y:.1f})")

        bounds = NSMakeRect(min_x, min_y, width, height)

        print(f"   最終邊界: origin=({min_x:.1f}, {min_y:.1f}), size=({width:.1f}, {height:.1f})\n")

        return bounds, is_multiline, accumulated_width

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
        print("\n=== 開始計算文字選取邊界 (統一方法) ===")

        # 取得選取的圖層
        try:
            selected_layers = tab.selectedLayers
            edit_view_width = Glyphs.editViewWidth
            font = Glyphs.font

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

        # 統一收集選取資訊
        print("\n📏 收集選取資訊:")
        info = self._collectSelectionInfo(selected_layers, tab)

        print(f"   有效字符數量: {len(info['valid_layers'])}")
        print(f"   選取總寬度: {info['selection_width']:.1f}")
        print(f"   包含換行符號: {info['has_newline']}")
        if info['has_newline']:
            print(f"   換行符號數量: {len(info['line_breaks'])}")
        print(f"   第一個選取字符索引: {info['first_selected_index']}")

        # 使用統一方法計算邊界
        result = self._calculateUnifiedBounds(info, edit_view_width, font, tab)

        if not result or result[0] is None:
            print("❌ 無法計算邊界")
            return None

        bounds, is_multiline, accumulated_width = result

        # 顯示最終結果
        center_x = bounds.origin.x + bounds.size.width / 2
        center_y = bounds.origin.y + bounds.size.height / 2

        print("\n✅ 最終結果:")
        print(f"   模式: {'跨行' if is_multiline else '單行'}")
        print(f"   邊界: origin=({bounds.origin.x:.1f}, {bounds.origin.y:.1f}), size=({bounds.size.width:.1f}, {bounds.size.height:.1f})")
        print(f"   中心點: ({center_x:.1f}, {center_y:.1f})")
        if is_multiline:
            print(f"   累積寬度: {accumulated_width:.1f}")
        print("=== 計算完成 ===\n")

        return bounds, is_multiline, accumulated_width

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
        """第二階段：延遲設定 viewPort（在 selectedLayerOrigin 更新後）

        使用統一的座標系統（相對於行首/索引 0）
        """
        try:
            tab = Glyphs.font.currentTab
            if not tab:
                return

            # 取得視口大小
            viewPort = tab.viewPort

            # 統一使用 selectedLayerOrigin（文字模式和節點模式都適用）
            origin = tab.selectedLayerOrigin

            print("\n📍 設定 viewport 定位 (統一座標系統)")
            print(f"   selectedLayerOrigin=({origin.x:.1f}, {origin.y:.1f})")
            print(f"   選取中心點 (font units)=({self._zoomCenterX:.1f}, {self._zoomCenterY:.1f})")
            print(f"   scale={self._zoomScale:.3f}")

            # 統一的 X 軸計算方式
            if self._isMultiline:
                # 跨行模式：中心點已經是「相對於行首」的座標
                # 步驟 1：反推行首（索引 0）在 view coordinates 的位置
                lineStartViewX = origin.x - (self._accumulatedWidth * self._zoomScale)

                # 步驟 2：中心點 = 行首 + 中心偏移（_zoomCenterX 已經是 editViewWidth / 2）
                centerViewX = lineStartViewX + (self._zoomCenterX * self._zoomScale)

                print("📍 跨行模式:")
                print(f"   累積寬度 (索引0到選取起點): {self._accumulatedWidth:.1f}")
                print(f"   行首 view X: {lineStartViewX:.1f}")
                print(f"   中心偏移 (font units): {self._zoomCenterX:.1f}")
                print(f"   最終中心 view X: {centerViewX:.1f}")
            else:
                # 單行模式：中心點相對於第一個字符
                centerViewX = origin.x + (self._zoomCenterX * self._zoomScale)

                print("📍 單行模式:")
                print(f"   selectedLayerOrigin.x: {origin.x:.1f}")
                print(f"   相對中心偏移: {self._zoomCenterX:.1f}")
                print(f"   最終中心 view X: {centerViewX:.1f}")

            # Y 軸計算相同
            centerViewY = origin.y + (self._zoomCenterY * self._zoomScale)
            print(f"   最終中心 view Y: {centerViewY:.1f}")

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