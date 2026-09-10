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
# 主题对照表和显示名称
# ============================================================
# 内部主题名 → QSS 字符串（换主题就是换这一整段样式）
XHANGGE_THEMES = {
    "pink": PINK_QSS,
    "light": LIGHT_QSS,
    "dark": DARK_QSS,
}

# 下拉框里显示的主题名字（带 emoji 更可爱）
THEME_LABELS = [
    ("pink", "🌸 粉色主题喵～"),
    ("light", "☀️ 亮色主题喵～"),
    ("dark", "🌙 暗色主题喵～"),
]
