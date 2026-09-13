# Author: xhangge
# This project is created by xhangge
"""
themes —— 界面主题（皮肤）中心
使用 Qt 的 QSS（Qt Style Sheets，类似网页的 CSS）给整个软件换皮肤。

包含三套主题：
- pink  粉色主题（默认，二次元可爱风）
- light 亮色主题（简洁白）
- dark  暗色主题（夜间护眼）

换主题的原理：把对应的 QSS 字符串设置到整个 QApplication 上，
所有界面上叫这些名字（objectName）的控件就会自动换上新样式。
"""

# ============================================================
# 粉色主题（默认）—— 二次元可爱风：粉色系 + 圆角 + 软绵绵
# ============================================================
PINK_QSS = """
/* ---- 全局默认样式：所有控件的基础底色和文字颜色 ---- */
QWidget {
    background: #FFF0F5;          /* 淡粉色背景 */
    color: #5A3A44;               /* 深粉色文字 */
    font-size: 14px;
}

/* （按钮的小手光标在代码里用 setCursor 设置，QSS 不支持 cursor 属性） */

/* ---- 顶部标题栏 ---- */
QFrame#TitleBar {
    background: #FFD9E8;
    border-bottom: 2px solid #FFB6D5;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}
QLabel#TitleIcon { background: transparent; font-size: 20px; }
QLabel#TitleLabel {
    background: transparent;
    color: #E0568C;
    font-size: 15px;
    font-weight: bold;
}
/* 标题栏右侧的功能按钮（置顶/侧边栏/最小化/最大化） */
QAbstractButton#TitleBtn {
    background: transparent;
    border: none;
    border-radius: 13px;
    color: #B85C7E;
    font-size: 14px;
}
QAbstractButton#TitleBtn:hover { background: #FFC2DA; }
/* 处于"按下/开启"状态的按钮（比如已开启置顶） */
QAbstractButton#TitleBtn:checked { background: #FF9EC4; color: white; }
/* 关闭按钮单独设计：悬停变红，符合大家的使用习惯 */
QAbstractButton#CloseBtn {
    background: transparent;
    border: none;
    border-radius: 13px;
    color: #B85C7E;
    font-size: 14px;
}
QAbstractButton#CloseBtn:hover { background: #FF6B81; color: white; }

/* ---- 左侧边栏 ---- */
QFrame#Sidebar {
    background: #FFE4EF;
    border-right: 2px solid #FFC2DA;
    border-bottom-left-radius: 14px;
}
QLabel#SidebarLogo {
    background: transparent;
    color: #E0568C;
    font-size: 16px;
    font-weight: bold;
}
/* "新建会话"大按钮：粉色渐变 + 大圆角 */
QAbstractButton#NewSessionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #FF9EC4, stop:1 #FF7BAC);
    color: white;
    border: none;
    border-radius: 18px;
    padding: 9px;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#NewSessionBtn:hover { background: #FF7BAC; }
QAbstractButton#NewSessionBtn:disabled { background: #E8C7D4; }

/* ---- 会话列表 ---- */
QListWidget#SessionList {
    background: transparent;
    border: none;
    font-size: 13px;
}
QListWidget#SessionList::item {
    background: white;
    border: 2px solid #FFD9E8;
    border-radius: 10px;
    padding: 8px 6px;
    margin: 3px 4px;
    color: #8A5566;
}
QListWidget#SessionList::item:selected {
    background: #FFD9E8;
    border-color: #FF9EC4;
    color: #E0568C;
    font-weight: bold;
}
QListWidget#SessionList::item:hover { border-color: #FFB6D5; }

/* ---- 侧边栏的分组框（我的信息 / 主题 / 学习模式） ---- */
QGroupBox {
    background: white;
    border: 2px solid #FFD9E8;
    border-radius: 12px;
    margin-top: 13px;
    padding: 8px 6px 6px 6px;
    font-weight: bold;
    color: #E0568C;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

/* ---- 输入框和下拉框 ---- */
QLineEdit, QComboBox {
    background: white;
    border: 2px solid #FFD9E8;
    border-radius: 10px;
    padding: 5px 8px;
    color: #5A3A44;
    font-size: 13px;
}
QLineEdit:focus, QComboBox:focus { border-color: #FF9EC4; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: white;
    border: 2px solid #FFD9E8;
    border-radius: 8px;
    selection-background-color: #FFD9E8;
    selection-color: #E0568C;
    outline: none;
}

/* ---- 聊天区 ---- */
QScrollArea#ChatScroll { background: #FFF0F5; border: none; }
QWidget#ChatContainer { background: transparent; }
QLabel#WelcomeLabel {
    background: transparent;
    color: #C4788F;
    font-size: 16px;
}
/* 头像（🐱 和 🐶）：透明背景，只是个大号 emoji */
QLabel#AvatarLabel { background: transparent; font-size: 22px; }
/* 用户消息气泡：粉色圆角气泡 + 白字 */
QFrame#userBubble {
    background: #FF9EC4;
    border-radius: 14px;
}
QFrame#userBubble QLabel {
    background: transparent;
    color: white;
    font-size: 14px;
}
/* 雪花喵回答气泡：白底圆角 + 淡粉描边 */
QFrame#assistantBubble {
    background: white;
    border: 2px solid #FFE4EF;
    border-radius: 14px;
}
/* 气泡里的富文本控件（能渲染 Markdown）：透明背景融入气泡 */
QFrame#assistantBubble QTextBrowser {
    background: transparent;
    border: none;
    color: #4A3540;
    font-size: 14px;
}
/* 出错时的气泡：红粉色系 */
QFrame#errorBubble {
    background: #FFF1F1;
    border: 2px solid #E58080;
    border-radius: 14px;
}
QFrame#errorBubble QTextBrowser {
    background: transparent;
    border: none;
    color: #C0392B;
    font-size: 14px;
}

/* ---- 底部输入区 ---- */
QTextEdit#InputEdit {
    background: white;
    border: 2px solid #FFD9E8;
    border-radius: 14px;
    padding: 8px 12px;
    font-size: 14px;
    color: #5A3A44;
}
QTextEdit#InputEdit:focus { border-color: #FF9EC4; }
QAbstractButton#SendBtn {
    background: #FF7BAC;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 8px 16px;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#SendBtn:hover { background: #FF5C9E; }
/* "停止"状态下的按钮换成橙色，提醒用户当前点它是停止 */
QAbstractButton#SendBtn[streaming="true"] {
    background: #FFA94D;
}
QAbstractButton#SendBtn[streaming="true"]:hover { background: #FF922B; }

/* ---- 弹窗（启动弹窗 / 重命名 / 确认） ---- */
QFrame#cuteDialogFrame {
    background: #FFF5F8;
    border: 3px solid #FFB6D5;
    border-radius: 18px;
}
QLabel#DialogTitle {
    background: transparent;
    color: #E0568C;
    font-size: 16px;
    font-weight: bold;
}
QLabel#DialogEmoji { background: transparent; font-size: 34px; }
QLabel#DialogText {
    background: transparent;
    color: #8A5566;
    font-size: 14px;
}
QAbstractButton#PrimaryBtn {
    background: #FF7BAC;
    color: white;
    border: none;
    border-radius: 14px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
}
QAbstractButton#PrimaryBtn:hover { background: #FF5C9E; }
QAbstractButton#SecondaryBtn {
    background: white;
    color: #E0568C;
    border: 2px solid #FF9EC4;
    border-radius: 14px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
}
QAbstractButton#SecondaryBtn:hover { background: #FFEBF3; }

/* ---- 右键菜单 ---- */
QMenu {
    background: white;
    border: 2px solid #FFD9E8;
    border-radius: 10px;
    color: #8A5566;
    padding: 4px;
}
QMenu::item { padding: 6px 26px; border-radius: 6px; }
QMenu::item:selected { background: #FFD9E8; color: #E0568C; }

/* ---- 滚动条：细圆角粉条，可爱不占地方 ---- */
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #FFC2DA;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #FFB0CE; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: #FFC2DA;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---- 右下角调整窗口大小的拖角 ---- */
QSizeGrip { background: transparent; }

/* ---- 鼠标悬停提示小气泡 ---- */
QToolTip {
    background: white;
    color: #E0568C;
    border: 2px solid #FFB6D5;
    border-radius: 8px;
    padding: 4px 8px;
}
"""

# ============================================================
# 亮色主题 —— 简洁白，办公学习场景不花哨
# ============================================================
LIGHT_QSS = """
QWidget {
    background: #F7F8FA;
    color: #3C4048;
    font-size: 14px;
}

QFrame#TitleBar {
    background: #FFFFFF;
    border-bottom: 2px solid #E4E7EC;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}
QLabel#TitleIcon { background: transparent; font-size: 20px; }
QLabel#TitleLabel {
    background: transparent;
    color: #4A5568;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#TitleBtn {
    background: transparent;
    border: none;
    border-radius: 13px;
    color: #7A8290;
    font-size: 14px;
}
QAbstractButton#TitleBtn:hover { background: #EDEFF3; }
QAbstractButton#TitleBtn:checked { background: #F8BBD0; color: #AD1457; }
QAbstractButton#CloseBtn {
    background: transparent;
    border: none;
    border-radius: 13px;
    color: #7A8290;
    font-size: 14px;
}
QAbstractButton#CloseBtn:hover { background: #FF6B81; color: white; }

QFrame#Sidebar {
    background: #F1F3F6;
    border-right: 2px solid #E4E7EC;
    border-bottom-left-radius: 14px;
}
QLabel#SidebarLogo {
    background: transparent;
    color: #4A5568;
    font-size: 16px;
    font-weight: bold;
}
QAbstractButton#NewSessionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #F48FB1, stop:1 #EC407A);
    color: white;
    border: none;
    border-radius: 18px;
    padding: 9px;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#NewSessionBtn:hover { background: #EC407A; }
QAbstractButton#NewSessionBtn:disabled { background: #D5DAE1; }

QListWidget#SessionList {
    background: transparent;
    border: none;
    font-size: 13px;
}
QListWidget#SessionList::item {
    background: white;
    border: 2px solid #E4E7EC;
    border-radius: 10px;
    padding: 8px 6px;
    margin: 3px 4px;
    color: #5A6270;
}
QListWidget#SessionList::item:selected {
    background: #FDE7EF;
    border-color: #F48FB1;
    color: #AD1457;
    font-weight: bold;
}
QListWidget#SessionList::item:hover { border-color: #F8BBD0; }

QGroupBox {
    background: white;
    border: 2px solid #E4E7EC;
    border-radius: 12px;
    margin-top: 13px;
    padding: 8px 6px 6px 6px;
    font-weight: bold;
    color: #4A5568;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QLineEdit, QComboBox {
    background: white;
    border: 2px solid #E4E7EC;
    border-radius: 10px;
    padding: 5px 8px;
    color: #3C4048;
    font-size: 13px;
}
QLineEdit:focus, QComboBox:focus { border-color: #F48FB1; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: white;
    border: 2px solid #E4E7EC;
    border-radius: 8px;
    selection-background-color: #FDE7EF;
    selection-color: #AD1457;
    outline: none;
}

QScrollArea#ChatScroll { background: #F7F8FA; border: none; }
QWidget#ChatContainer { background: transparent; }
QLabel#WelcomeLabel {
    background: transparent;
    color: #9AA1AC;
    font-size: 16px;
}
QLabel#AvatarLabel { background: transparent; font-size: 22px; }
QFrame#userBubble {
    background: #F06292;
    border-radius: 14px;
}
QFrame#userBubble QLabel {
    background: transparent;
    color: white;
    font-size: 14px;
}
QFrame#assistantBubble {
    background: white;
    border: 2px solid #E4E7EC;
    border-radius: 14px;
}
QFrame#assistantBubble QTextBrowser {
    background: transparent;
    border: none;
    color: #333A44;
    font-size: 14px;
}
QFrame#errorBubble {
    background: #FFF3F3;
    border: 2px solid #E58080;
    border-radius: 14px;
}
QFrame#errorBubble QTextBrowser {
    background: transparent;
    border: none;
    color: #C0392B;
    font-size: 14px;
}

QTextEdit#InputEdit {
    background: white;
    border: 2px solid #E4E7EC;
    border-radius: 14px;
    padding: 8px 12px;
    font-size: 14px;
    color: #3C4048;
}
QTextEdit#InputEdit:focus { border-color: #F48FB1; }
QAbstractButton#SendBtn {
    background: #EC407A;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 8px 16px;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#SendBtn:hover { background: #D81B60; }
QAbstractButton#SendBtn[streaming="true"] { background: #FFA94D; }
QAbstractButton#SendBtn[streaming="true"]:hover { background: #FF922B; }

QFrame#cuteDialogFrame {
    background: #FFFFFF;
    border: 3px solid #F8BBD0;
    border-radius: 18px;
}
QLabel#DialogTitle {
    background: transparent;
    color: #4A5568;
    font-size: 16px;
    font-weight: bold;
}
QLabel#DialogEmoji { background: transparent; font-size: 34px; }
QLabel#DialogText {
    background: transparent;
    color: #5A6270;
    font-size: 14px;
}
QAbstractButton#PrimaryBtn {
    background: #EC407A;
    color: white;
    border: none;
    border-radius: 14px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
}
QAbstractButton#PrimaryBtn:hover { background: #D81B60; }
QAbstractButton#SecondaryBtn {
    background: white;
    color: #AD1457;
    border: 2px solid #F48FB1;
    border-radius: 14px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
}
QAbstractButton#SecondaryBtn:hover { background: #FDE7EF; }

QMenu {
    background: white;
    border: 2px solid #E4E7EC;
    border-radius: 10px;
    color: #5A6270;
    padding: 4px;
}
QMenu::item { padding: 6px 26px; border-radius: 6px; }
QMenu::item:selected { background: #FDE7EF; color: #AD1457; }

QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #D5DAE1;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #C2C8D1; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: #D5DAE1;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QSizeGrip { background: transparent; }
QToolTip {
    background: white;
    color: #4A5568;
    border: 2px solid #F8BBD0;
    border-radius: 8px;
    padding: 4px 8px;
}
"""

# ============================================================
# 暗色主题 —— 夜间护眼，深紫黑底 + 保留品牌粉点缀
# ============================================================
DARK_QSS = """
QWidget {
    background: #2A2330;
    color: #E9E0E8;
    font-size: 14px;
}

QFrame#TitleBar {
    background: #332A3B;
    border-bottom: 2px solid #453A4F;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}
QLabel#TitleIcon { background: transparent; font-size: 20px; }
QLabel#TitleLabel {
    background: transparent;
    color: #F3C6D8;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#TitleBtn {
    background: transparent;
    border: none;
    border-radius: 13px;
    color: #C0AEBB;
    font-size: 14px;
}
QAbstractButton#TitleBtn:hover { background: #453A4F; }
QAbstractButton#TitleBtn:checked { background: #FF7BAC; color: white; }
QAbstractButton#CloseBtn {
    background: transparent;
    border: none;
    border-radius: 13px;
    color: #C0AEBB;
    font-size: 14px;
}
QAbstractButton#CloseBtn:hover { background: #FF6B81; color: white; }

QFrame#Sidebar {
    background: #332A3B;
    border-right: 2px solid #453A4F;
    border-bottom-left-radius: 14px;
}
QLabel#SidebarLogo {
    background: transparent;
    color: #F3C6D8;
    font-size: 16px;
    font-weight: bold;
}
QAbstractButton#NewSessionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #D95C93, stop:1 #B8457A);
    color: white;
    border: none;
    border-radius: 18px;
    padding: 9px;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#NewSessionBtn:hover { background: #B8457A; }
QAbstractButton#NewSessionBtn:disabled { background: #4A3D56; }

QListWidget#SessionList {
    background: transparent;
    border: none;
    font-size: 13px;
}
QListWidget#SessionList::item {
    background: #3A3043;
    border: 2px solid #453A4F;
    border-radius: 10px;
    padding: 8px 6px;
    margin: 3px 4px;
    color: #C0AEBB;
}
QListWidget#SessionList::item:selected {
    background: #4A3D56;
    border-color: #FF7BAC;
    color: #FFC2DA;
    font-weight: bold;
}
QListWidget#SessionList::item:hover { border-color: #B8457A; }

QGroupBox {
    background: #3A3043;
    border: 2px solid #453A4F;
    border-radius: 12px;
    margin-top: 13px;
    padding: 8px 6px 6px 6px;
    font-weight: bold;
    color: #F3C6D8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QLineEdit, QComboBox {
    background: #2A2330;
    border: 2px solid #453A4F;
    border-radius: 10px;
    padding: 5px 8px;
    color: #E9E0E8;
    font-size: 13px;
}
QLineEdit:focus, QComboBox:focus { border-color: #FF7BAC; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #3A3043;
    border: 2px solid #453A4F;
    border-radius: 8px;
    selection-background-color: #4A3D56;
    selection-color: #FFC2DA;
    outline: none;
}

QScrollArea#ChatScroll { background: #2A2330; border: none; }
QWidget#ChatContainer { background: transparent; }
QLabel#WelcomeLabel {
    background: transparent;
    color: #8F7D9A;
    font-size: 16px;
}
QLabel#AvatarLabel { background: transparent; font-size: 22px; }
QFrame#userBubble {
    background: #B8457A;
    border-radius: 14px;
}
QFrame#userBubble QLabel {
    background: transparent;
    color: white;
    font-size: 14px;
}
QFrame#assistantBubble {
    background: #3A3043;
    border: 2px solid #4A3D56;
    border-radius: 14px;
}
QFrame#assistantBubble QTextBrowser {
    background: transparent;
    border: none;
    color: #E9E0E8;
    font-size: 14px;
}
QFrame#errorBubble {
    background: #4A2E33;
    border: 2px solid #8A4A55;
    border-radius: 14px;
}
QFrame#errorBubble QTextBrowser {
    background: transparent;
    border: none;
    color: #FFB4B4;
    font-size: 14px;
}

QTextEdit#InputEdit {
    background: #332A3B;
    border: 2px solid #453A4F;
    border-radius: 14px;
    padding: 8px 12px;
    font-size: 14px;
    color: #E9E0E8;
}
QTextEdit#InputEdit:focus { border-color: #FF7BAC; }
QAbstractButton#SendBtn {
    background: #D95C93;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 8px 16px;
    font-size: 15px;
    font-weight: bold;
}
QAbstractButton#SendBtn:hover { background: #B8457A; }
QAbstractButton#SendBtn[streaming="true"] { background: #B8702B; }
QAbstractButton#SendBtn[streaming="true"]:hover { background: #A06122; }

QFrame#cuteDialogFrame {
    background: #332A3B;
    border: 3px solid #B8457A;
    border-radius: 18px;
}
QLabel#DialogTitle {
    background: transparent;
    color: #F3C6D8;
    font-size: 16px;
    font-weight: bold;
}
QLabel#DialogEmoji { background: transparent; font-size: 34px; }
QLabel#DialogText {
    background: transparent;
    color: #C0AEBB;
    font-size: 14px;
}
QAbstractButton#PrimaryBtn {
    background: #D95C93;
    color: white;
    border: none;
    border-radius: 14px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
}
QAbstractButton#PrimaryBtn:hover { background: #B8457A; }
QAbstractButton#SecondaryBtn {
    background: #332A3B;
    color: #F3C6D8;
    border: 2px solid #D95C93;
    border-radius: 14px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: bold;
}
QAbstractButton#SecondaryBtn:hover { background: #453A4F; }

QMenu {
    background: #3A3043;
    border: 2px solid #453A4F;
    border-radius: 10px;
    color: #C0AEBB;
    padding: 4px;
}
QMenu::item { padding: 6px 26px; border-radius: 6px; }
QMenu::item:selected { background: #4A3D56; color: #FFC2DA; }

QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #554862;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #6A5A7A; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: #554862;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QSizeGrip { background: transparent; }
QToolTip {
    background: #3A3043;
    color: #F3C6D8;
    border: 2px solid #B8457A;
    border-radius: 8px;
    padding: 4px 8px;
}
"""

# ============================================================
# 设置窗口的样式（新增组件）—— 用「一个模板 + 三套配色」生成
# ============================================================
# 为什么这么写？
# 上面三套主题是分别手写的，样式条数多、颜色也各不相同。
# 但「设置窗口」是这次新加的，它的结构在三套主题下完全一样，
# 只有颜色不一样。如果照旧复制三遍，以后改一个圆角就要改三处，
# 很容易漏掉其中一处导致某个主题变丑。
#
# 所以这里换个更省事的做法：
# 1. 先写一份「模板」，把所有颜色都留成 {xxx} 这样的空位；
# 2. 再给每套主题准备一张「配色表」（字典），告诉模板每个空位填什么颜色；
# 3. 用 .format(**配色表) 把空位填上，就得到三份真正的 QSS。
#
# 小提醒：模板里如果要写 QSS 本来就有的大括号（比如 QWidget { ... }），
# .format() 会把它当成空位。所以模板里的大括号要写成双份 {{ }}，
# .format() 处理完之后就会变回单个 { }。
_XHANGGE_SETTINGS_QSS_TEMPLATE = """
/* ==================== 主窗口整体（圆角矩形） ==================== */
/* 为什么这些规则放在"追加段"里：主窗口本身是无边框+透明背景的，
   靠最外层这个 QFrame 画出圆角矩形和一圈细描边。
   窗口内的部件各管一个角：
   - 标题栏：左上/右上圆角（写死在三套主题的 TitleBar 规则里）
   - 侧边栏：左下圆角（同上）
   - ChatAreaRoot：右下圆角（下面这条）
   拼起来就是完整的圆角窗口喵。 */

QFrame#MainWindowFrame {{
    background: {win_bg};
    border: 2px solid {accent};
    border-radius: 14px;
}}

/* 聊天区最外层：画底色 + 右下圆角 */
QWidget#ChatAreaRoot {{
    background: {win_bg};
    border-bottom-right-radius: 14px;
}}
/* 滚动区和输入栏变透明：让 ChatAreaRoot 的圆角露出来
   （它们自己画不透明的方角会把圆角盖掉） */
QScrollArea#ChatScroll {{ background: transparent; border: none; }}
QWidget#InputBar {{ background: transparent; }}
QScrollArea#ChatScroll > QWidget > QWidget {{ background: transparent; }}

/* ==================== 新增组件（设置窗口 + 聊天区工具条） ==================== */

/* ---- 聊天区输入框上方的工具条（药丸按钮一排） ---- */
QFrame#ToolCapsuleBar {{ background: transparent; }}
QAbstractButton#CapsuleBtn {{
    background: {card_bg};
    color: {body_fg};
    border: 2px solid {border};
    border-radius: 13px;
    padding: 4px 12px;
    font-size: 12px;
}}
QAbstractButton#CapsuleBtn:hover {{
    border-color: {accent};
    color: {accent_text};
}}
QAbstractButton#CapsuleBtn:disabled {{
    background: {disabled_bg};
    color: {muted_fg};
}}

/* ---- Agent 步骤卡片（Agent 干活时显示它正在做什么） ---- */
QFrame#agentStepCard {{
    background: {card_bg};
    border: 2px dashed {border_strong};
    border-radius: 12px;
}}
QFrame#agentStepCard QLabel {{ background: transparent; }}
QLabel#AgentStepTitle {{
    color: {title_fg};
    font-size: 12px;
    font-weight: bold;
}}
QLabel#AgentStepText {{
    color: {muted_fg};
    font-size: 12px;
}}

/* ==================== 知识库窗口 ==================== */

/* 左侧库列表（外观和设置窗导航一致，复用同一套配色） */
QFrame#KbPanel {{
    background: {nav_bg};
    border: none;
    border-bottom-left-radius: 15px;
}}
QListWidget#KbList {{
    background: transparent;
    border: none;
    font-size: 13px;
    outline: none;
}}
QListWidget#KbList::item {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 8px 8px;
    margin: 3px 6px;
    color: {nav_fg};
}}
QListWidget#KbList::item:hover {{ background: {nav_hover}; }}
QListWidget#KbList::item:selected {{
    background: {nav_sel_bg};
    color: {nav_sel_fg};
    font-weight: bold;
}}

/* 拖拽投放区：虚线框，像便利店门口的"欢迎光临"地垫 */
QFrame#KbDropZone {{
    background: {card_bg};
    border: 2px dashed {border_strong};
    border-radius: 14px;
}}

/* 文件列表里的一行 */
QFrame#KbFileRow {{
    background: {card_bg};
    border: 2px solid {border};
    border-radius: 10px;
}}
QFrame#KbFileRow QLabel {{ background: transparent; font-size: 12px; }}

/* 容量提示条上方的字 */
QLabel#KbCapTitle {{
    background: transparent;
    color: {title_fg};
    font-size: 13px;
    font-weight: bold;
}}

/* ==================== 设置窗口 ==================== */

/* ---- 设置窗口的外框（无边框窗口，自己画圆角和描边） ---- */
QFrame#SettingsFrame {{
    background: {win_bg};
    border: 3px solid {accent};
    border-radius: 18px;
}}

/* ---- 设置窗口自己的小标题栏 ---- */
QFrame#SettingsTitleBar {{
    background: {bar_bg};
    border: none;
    border-top-left-radius: 15px;
    border-top-right-radius: 15px;
}}
QLabel#SettingsTitleLabel {{
    background: transparent;
    color: {title_fg};
    font-size: 15px;
    font-weight: bold;
}}

/* ---- 左侧导航（🧠模型 / 🤖Agent / 🔍搜索 / 🎨外观 / ℹ️关于） ---- */
QFrame#SettingsNavPanel {{
    background: {nav_bg};
    border: none;
    border-bottom-left-radius: 15px;
}}
QListWidget#SettingsNav {{
    background: transparent;
    border: none;
    font-size: 13px;
    outline: none;                 /* 去掉选中时那个虚线框，更干净 */
}}
QListWidget#SettingsNav::item {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 10px;
    margin: 3px 6px;
    color: {nav_fg};
}}
QListWidget#SettingsNav::item:hover {{ background: {nav_hover}; }}
QListWidget#SettingsNav::item:selected {{
    background: {nav_sel_bg};
    color: {nav_sel_fg};
    font-weight: bold;
}}
/* 灰置的导航项（比如「🎨 外观喵」占位，还没做好）：变浅 + 不响应悬停 */
QListWidget#SettingsNav::item:disabled {{
    color: {muted_fg};
    background: transparent;
}}

/* ---- 右侧内容区 ---- */
QScrollArea#SettingsScroll {{ background: transparent; border: none; }}
QWidget#SettingsPage {{ background: transparent; }}
/* 每一页顶部的大标题，例如「🧠 模型设置喵」 */
QLabel#SettingsPageTitle {{
    background: transparent;
    color: {title_fg};
    font-size: 17px;
    font-weight: bold;
}}
/* 灰色小字说明，用来解释这个开关是干嘛的 */
QLabel#SettingsHint {{
    background: transparent;
    color: {muted_fg};
    font-size: 12px;
}}
/* 普通说明文字 */
QLabel#SettingsText {{
    background: transparent;
    color: {body_fg};
    font-size: 13px;
}}
/* 一块块的白色卡片，把相关的设置圈在一起，看起来不乱 */
QFrame#SettingsCard {{
    background: {card_bg};
    border: 2px solid {border};
    border-radius: 14px;
}}
QFrame#SettingsCard QLabel {{ background: transparent; }}
/* 卡片顶部的小标题，例如「本地模型喵」 */
QLabel#SettingsCardTitle {{
    background: transparent;
    color: {title_fg};
    font-size: 14px;
    font-weight: bold;
}}
/* 一条细细的分隔线 */
QFrame#SettingsSeparator {{
    background: {border};
    border: none;
    max-height: 2px;
    min-height: 2px;
}}

/* ---- 单选按钮：本地模型 / 在线 API 二选一（互斥就靠它） ---- */
QRadioButton {{
    background: transparent;
    color: {body_fg};
    font-size: 13px;
    spacing: 8px;                  /* 圆点和文字之间的距离 */
    padding: 3px 0;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 9px;            /* 半径 = 宽度的一半 + 边框，才是正圆 */
    border: 2px solid {border_strong};
    background: {card_bg};
}}
QRadioButton::indicator:hover {{ border-color: {accent}; }}
/* 选中时：中间填上主题色的实心点（用渐变模拟「甜甜圈」效果） */
QRadioButton::indicator:checked {{
    border: 2px solid {accent};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                fx:0.5, fy:0.5,
                stop:0 {accent}, stop:0.55 {accent},
                stop:0.6 {card_bg}, stop:1 {card_bg});
}}
QRadioButton:disabled {{ color: {muted_fg}; }}

/* ---- 勾选框 ---- */
QCheckBox {{
    background: transparent;
    color: {body_fg};
    font-size: 13px;
    spacing: 8px;
    padding: 3px 0;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 2px solid {border_strong};
    background: {card_bg};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{
    border: 2px solid {accent};
    background: {accent};
}}
QCheckBox:disabled {{ color: {muted_fg}; }}

/* ---- 数字输入框（超时秒数、上下文条数之类） ---- */
QSpinBox {{
    background: {card_bg};
    border: 2px solid {border};
    border-radius: 10px;
    padding: 4px 6px;
    color: {body_fg};
    font-size: 13px;
}}
QSpinBox:focus {{ border-color: {accent}; }}
QSpinBox::up-button, QSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 16px;
}}

/* ---- 输入框被禁用时的样子 ---- */
/* 为什么要专门写：Qt 默认给禁用的输入框只做很轻微的变化，
   在我们这种白底卡片上几乎看不出来，用户会一直去点一个点不了的框。
   变灰之后就一眼能看出"这个现在不能填"。 */
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: {disabled_bg};
    color: {muted_fg};
    border-color: {border};
}}

/* ---- 设置窗里的按钮 ---- */
/* 主要动作按钮：保存、测试连接、开始下载 */
QAbstractButton#SettingsBtn {{
    background: {accent};
    color: {on_accent};
    border: none;
    border-radius: 12px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: bold;
}}
QAbstractButton#SettingsBtn:hover {{ background: {accent_hover}; }}
/* 按钮被禁用时（比如正在下载中不许再点）：变灰，让用户一眼看出点不了 */
QAbstractButton#SettingsBtn:disabled {{
    background: {disabled_bg};
    color: {muted_fg};
}}
/* 次要动作按钮：选择文件夹、取消 */
QAbstractButton#SettingsGhostBtn {{
    background: {card_bg};
    color: {accent_text};
    border: 2px solid {accent};
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: bold;
}}
QAbstractButton#SettingsGhostBtn:hover {{ background: {ghost_hover}; }}
QAbstractButton#SettingsGhostBtn:disabled {{
    background: {disabled_bg};
    color: {muted_fg};
    border-color: {border};
}}
/* 危险动作按钮：删除模型配置（红色，提醒用户这一步不可逆） */
QAbstractButton#SettingsDangerBtn {{
    background: transparent;
    color: #E5544B;
    border: 2px solid #E5544B;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: bold;
}}
QAbstractButton#SettingsDangerBtn:hover {{ background: #E5544B; color: white; }}

/* ---- 状态小药丸：显示「✅ 已安装喵 / ⚠️ 未安装喵」 ---- */
QLabel#SettingsBadgeOk {{
    background: {ok_bg};
    color: {ok_fg};
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: bold;
}}
QLabel#SettingsBadgeWarn {{
    background: {warn_bg};
    color: {warn_fg};
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: bold;
}}

/* ---- 关于页里的超链接文字 ---- */
QLabel#SettingsLink {{
    background: transparent;
    color: {accent_text};
    font-size: 13px;
}}
"""

# 三套主题各自的配色表。键名要和上面模板里的 {空位} 一一对应。
_XHANGGE_SETTINGS_PALETTES = {
    # 粉色主题：延续淡粉 + 桃红的可爱风
    "pink": {
        "win_bg": "#FFF5F8",
        "bar_bg": "#FFD9E8",
        "nav_bg": "#FFE4EF",
        "card_bg": "#FFFFFF",
        "border": "#FFD9E8",
        "border_strong": "#FFB6D5",
        "accent": "#FF7BAC",
        "accent_hover": "#FF5C9E",
        "accent_text": "#E0568C",
        "on_accent": "#FFFFFF",
        "ghost_hover": "#FFEBF3",
        "title_fg": "#E0568C",
        "body_fg": "#5A3A44",
        "nav_fg": "#8A5566",
        "nav_hover": "#FFD9E8",
        "nav_sel_bg": "#FF9EC4",
        "nav_sel_fg": "#FFFFFF",
        "muted_fg": "#C4A0AE",
        "disabled_bg": "#F3E3EA",
        "ok_bg": "#E4F7EA",
        "ok_fg": "#2E8B57",
        "warn_bg": "#FFF3DC",
        "warn_fg": "#B8791F",
    },
    # 亮色主题：灰白底 + 玫红点缀，克制一些
    "light": {
        "win_bg": "#FFFFFF",
        "bar_bg": "#F1F3F6",
        "nav_bg": "#F7F8FA",
        "card_bg": "#FFFFFF",
        "border": "#E4E7EC",
        "border_strong": "#C9CFD8",
        "accent": "#EC407A",
        "accent_hover": "#D81B60",
        "accent_text": "#AD1457",
        "on_accent": "#FFFFFF",
        "ghost_hover": "#FDE7EF",
        "title_fg": "#4A5568",
        "body_fg": "#3C4048",
        "nav_fg": "#5A6270",
        "nav_hover": "#EDEFF3",
        "nav_sel_bg": "#FDE7EF",
        "nav_sel_fg": "#AD1457",
        "muted_fg": "#9AA2AE",
        "disabled_bg": "#EDEFF3",
        "ok_bg": "#E6F6EC",
        "ok_fg": "#237A47",
        "warn_bg": "#FFF4E0",
        "warn_fg": "#A9711A",
    },
    # 暗色主题：紫灰底 + 暗玫红，夜里不刺眼
    "dark": {
        "win_bg": "#2A2330",
        "bar_bg": "#332A3B",
        "nav_bg": "#332A3B",
        "card_bg": "#3A3043",
        "border": "#453A4F",
        "border_strong": "#5A4C66",
        "accent": "#D95C93",
        "accent_hover": "#B8457A",
        "accent_text": "#FFC2DA",
        "on_accent": "#FFFFFF",
        "ghost_hover": "#4A3D56",
        "title_fg": "#F3C6D8",
        "body_fg": "#E9E0E8",
        "nav_fg": "#C0AEBB",
        "nav_hover": "#453A4F",
        "nav_sel_bg": "#B8457A",
        "nav_sel_fg": "#FFFFFF",
        "muted_fg": "#8F7D9A",
        "disabled_bg": "#3E3548",
        "ok_bg": "#26402F",
        "ok_fg": "#7BD6A0",
        "warn_bg": "#443521",
        "warn_fg": "#E5B866",
    },
}


def _xhangge_settings_qss(theme_key: str) -> str:
    """
    把「模板 + 某套配色」拼成这套主题的设置窗口样式。

    参数 theme_key：主题名，"pink" / "light" / "dark"
    返回：填好颜色的 QSS 字符串
    """
    palette = _XHANGGE_SETTINGS_PALETTES[theme_key]
    return _XHANGGE_SETTINGS_QSS_TEMPLATE.format(**palette)


# ============================================================
# 主题对照表和显示名称
# ============================================================
# 内部主题名 → QSS 字符串（换主题就是换这一整段样式）
# 这里把「原来的主题样式」和「新增的设置窗口样式」拼在一起：
# QSS 是从上往下生效的，后面的规则会覆盖前面同名的规则，
# 所以设置窗口的样式放在后面，正好能盖住通用样式。
XHANGGE_THEMES = {
    "pink": PINK_QSS + _xhangge_settings_qss("pink"),
    "light": LIGHT_QSS + _xhangge_settings_qss("light"),
    "dark": DARK_QSS + _xhangge_settings_qss("dark"),
}

# 下拉框里显示的主题名字（带 emoji 更可爱）
THEME_LABELS = [
    ("pink", "🌸 粉色主题喵～"),
    ("light", "☀️ 亮色主题喵～"),
    ("dark", "🌙 暗色主题喵～"),
]
