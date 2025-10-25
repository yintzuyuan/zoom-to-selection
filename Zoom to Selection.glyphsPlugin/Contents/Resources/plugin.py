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
            tab = Glyphs.font.currentTab
            if not tab:
                return

            layer = tab.activeLayer()
            if not layer:
                return

            # 使用 boundsOfSelection() 方法
            bounds = layer.boundsOfSelection()
            if not bounds:
                return

            # 取得視口大小
            viewPort = tab.viewPort

            # 處理零尺寸選取
            selWidth = bounds.size.width
            selHeight = bounds.size.height

            # 如果寬度或高度為零,使用最小值計算 scale
            MIN_SIZE = 100  # font units

            if selWidth == 0 and selHeight == 0:
                # 單點選取:使用固定縮放
                targetSize = MIN_SIZE
            elif selWidth == 0:
                # 垂直線:使用高度
                targetSize = selHeight * 1.25
            elif selHeight == 0:
                # 水平線:使用寬度
                targetSize = selWidth * 1.25
            else:
                # 正常選取:使用較大維度
                targetSize = max(selWidth, selHeight) * 1.25

            # 計算選取中心點(font units)
            centerX = bounds.origin.x + selWidth / 2
            centerY = bounds.origin.y + selHeight / 2

            # 計算所需 scale
            newScale = min(viewPort.size.width, viewPort.size.height) / targetSize

            # 設定 scale
            tab.scale = newScale

            # 觸發 runloop,避免與 Glyphs 自動滾動衝突
            print()

            # 在新 scale 下重新讀取 selectedLayerOrigin
            origin = tab.selectedLayerOrigin

            # 計算選取中心在 view coordinates 的位置
            centerViewX = origin.x + (centerX * newScale)
            centerViewY = origin.y + (centerY * newScale)

            # 設定 viewPort
            tab.viewPort = NSMakeRect(
                centerViewX - viewPort.size.width / 2,
                centerViewY - viewPort.size.height / 2,
                viewPort.size.width,
                viewPort.size.height
            )

        except Exception as e:
            print(f"Zoom to Selection Error: {e}")
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

        # 檢查是否有選取內容 (允許零尺寸選取)
        selectionBounds = layer.boundsOfSelection()
        if not selectionBounds:
            return False

        return True