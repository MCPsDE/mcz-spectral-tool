import hashlib
import json
import logging
import re
import subprocess
import os
import sys
import tempfile
import time
import tkinter as tk
from tkinter import messagebox, ttk, filedialog, scrolledtext
import threading
import tkinter.ttk as ttk
import webbrowser
from packaging import version
import requests
#pyinstaller -F -w -i asd.ico --add-data "asd.ico;." 合谱工具GUI.py
# 打包新版本
'''
pyinstaller -F -w -i asd.ico  main.py -n "mcz-spectral-toolv2.4.1.exe"

# 生成更新信息
python generate_update_info.py'''
# 当前版本号 - 每次发布新版本时更新这个值
CURRENT_VERSION = "2.4.1"
import urllib
# 资源路径处理函数
# 配置日志
def setup_logging():
    log_dir = os.path.join(os.path.dirname(sys.executable), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"update_{time.strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='a'
    )
    return logging.getLogger()

logger = setup_logging()

def check_for_updates():
    """检查是否有新版本可用"""
    try:
        logger.info("开始检查更新...")
        # 获取版本信息
        response = requests.get(
            "https://gitee.com/mcpsde/mcz-spectral-tool/raw/master/update.json",
            timeout=10
        )
        response.raise_for_status()
        update_info = response.json()
        logger.info(f"获取到更新信息: {json.dumps(update_info, ensure_ascii=False)}")
        
        # 比较版本
        if version.parse(update_info["version"]) > version.parse(CURRENT_VERSION):
            logger.info(f"发现新版本: {update_info['version']}")
            return {
                "available": True,
                "version": update_info["version"],
                "download_url": update_info["download_url"],
                "release_notes": "\n".join(update_info["changelog"]),
                "file_size": update_info.get("file_size", 0),
                "sha256": update_info.get("sha256", "")
            }
    except requests.exceptions.RequestException as e:
        logger.error(f"网络错误: {str(e)}")
    except Exception as e:
        logger.error(f"检查更新失败: {str(e)}", exc_info=True)
    
    logger.info("未发现新版本")
    return {"available": False}

def verify_file_integrity(file_path, expected_size, expected_hash):
    """验证文件完整性和哈希值"""
    logger.info(f"开始验证文件: {file_path}")
    try:
        # 检查文件大小
        #actual_size = os.path.getsize(file_path)
        #if actual_size != expected_size:
        #    logger.error(f"文件大小不匹配: {actual_size} vs {expected_size}")
        #    return False, f"文件大小不匹配: {actual_size} vs {expected_size}"
        
        # 检查SHA256哈希值
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(65536)  # 64KB chunks
                if not data:
                    break
                sha256.update(data)
        
        actual_hash = sha256.hexdigest()
        if actual_hash != expected_hash:
            logger.error(f"哈希值不匹配: {actual_hash} vs {expected_hash}")
            return False, f"哈希值不匹配: {actual_hash} vs {expected_hash}"
        
        logger.info("文件验证成功")
        return True, ""
    except Exception as e:
        logger.error(f"文件验证失败: {str(e)}", exc_info=True)
        return False, f"文件验证失败: {str(e)}"

def create_restart_script(new_exe_path, app_dir):
    """创建重启脚本"""
    try:
        logger.info("创建重启脚本...")
        bat_path = os.path.join(app_dir, "restart.bat")
        current_exe = sys.executable
        current_exe_name = os.path.basename(current_exe)
        
        with open(bat_path, 'w', encoding='gbk') as f:  # 使用GBK编码确保中文兼容
            f.write("@echo off\n")
            f.write("chcp 65001 >nul\n")  # 设置UTF-8编码
            f.write("echo 正在更新应用程序...\n")
            f.write("timeout /t 3 /nobreak >nul\n")
            f.write(f'echo 正在替换文件: "{current_exe_name}"\n')
            f.write(f'del /F /Q "{current_exe}"\n')
            f.write(f'copy /Y "{new_exe_path}" "{app_dir}\\" >nul\n')
            f.write(f'start "" "{app_dir}\\{os.path.basename(new_exe_path)}"\n')
            f.write("echo 更新完成，正在启动新版本...\n")
            f.write("timeout /t 2 /nobreak >nul\n")
            f.write("del \"%~f0\"\n")  # 删除自身
        
        logger.info(f"创建重启脚本成功: {bat_path}")
        return bat_path
    except Exception as e:
        logger.error(f"创建重启脚本失败: {str(e)}", exc_info=True)
        raise

def download_with_progress(url, file_path, progress_callback=None):
    """带进度回调的下载函数"""
    try:
        logger.info(f"开始下载: {url}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024 * 1024  # 1 MB
        downloaded = 0
        
        with open(file_path, 'wb') as f:
            for data in response.iter_content(block_size):
                f.write(data)
                downloaded += len(data)
                if total_size > 0 and progress_callback:
                    percent = min(100, int(downloaded * 100 / total_size))
                    progress_callback(percent)
        
        logger.info(f"下载完成: {file_path}")
        return True
    except Exception as e:
        logger.error(f"下载失败: {str(e)}", exc_info=True)
        return False

def start_update(update_info, dialog=None):
    """开始更新过程"""
    try:
        logger.info("开始更新过程...")
        # 获取当前应用目录
        app_dir = os.path.dirname(sys.executable)
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        file_name = update_info["download_url"].split('/')[-1]
        new_exe_path = os.path.join(temp_dir, file_name)
        
        # 如果有对话框，更新状态
        if dialog and hasattr(dialog, 'status_label'):
            dialog.status_label.config(text="正在下载更新...")
            dialog.update()
        
        # 下载新版本（带进度回调）
        def update_progress(percent):
            if dialog and hasattr(dialog, 'progress') and hasattr(dialog, 'percent_label'):
                dialog.progress['value'] = percent
                dialog.percent_label.config(text=f"{percent}%")
                dialog.update()
        
        success = download_with_progress(update_info["download_url"], new_exe_path, update_progress)
        if not success:
            raise Exception("下载失败")
        
        # 验证文件完整性
        if dialog and hasattr(dialog, 'status_label'):
            dialog.status_label.config(text="正在验证文件...")
            dialog.update()
        
        if update_info.get("file_size") and update_info.get("sha256"):
            valid, reason = verify_file_integrity(
                new_exe_path, 
                update_info["file_size"], 
                update_info["sha256"]
            )
            if not valid:
                raise Exception(f"文件验证失败: {reason}")
        
        # 创建重启脚本
        if dialog and hasattr(dialog, 'status_label'):
            dialog.status_label.config(text="准备重启...")
            dialog.update()
        
        bat_path = create_restart_script(new_exe_path, app_dir)
        
        # 重启应用
        restart_application(bat_path)
        
    except Exception as e:
        logger.error(f"更新失败: {str(e)}", exc_info=True)
        error_msg = f"更新过程中出错: {str(e)}"
        
        if dialog:
            if hasattr(dialog, 'status_label'):
                dialog.status_label.config(text=error_msg)
            dialog.update()
            time.sleep(2)
            dialog.destroy()
        
        # 提供手动下载选项
        if messagebox.askyesno("更新失败", f"{error_msg}\n\n是否手动下载新版本？"):
            webbrowser.open(update_info["download_url"])
    finally:
        # 不清理临时目录，重启脚本会处理
        pass

def restart_application(bat_path):
    """重启应用程序"""
    try:
        messagebox.showerror("更新完毕!请重新启动")
        
        # 退出当前应用
        sys.exit(0)
    except Exception as e:
        logger.error(f"重启失败: {str(e)}", exc_info=True)
        messagebox.showerror("重启失败", f"无法重启应用程序: {str(e)}\n请手动运行: {bat_path}")

def check_updates_on_start():
    """应用程序启动时检查更新"""
    # 延迟检查，让主界面先显示
    root.after(2000, lambda: threading.Thread(target=check_and_show_updates, daemon=True).start())

def check_and_show_updates():
    """检查并显示更新"""
    try:
        update_info = check_for_updates()
        if update_info["available"]:
            # 在主线程中显示更新对话框
            root.after(0, lambda: show_update_dialog(update_info))
    except Exception as e:
        logger.error(f"更新检查失败: {str(e)}", exc_info=True)

def show_update_dialog(update_info):
    """显示更新对话框"""
    try:
        logger.info("显示更新对话框...")
        dialog = tk.Toplevel(root)
        dialog.title("发现新版本")
        dialog.geometry("809x500")
        dialog.transient(root)
        dialog.grab_set()
        
        # 设置窗口图标
        try:
            dialog.iconbitmap(resource_path("asd.ico"))
        except:
            pass
        
        # 创建框架
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            frame, 
            text=f"发现新版本 {update_info['version']} (当前版本: {CURRENT_VERSION})",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=10)
        
        # 更新说明
        notes_frame = ttk.LabelFrame(frame, text="更新说明")
        notes_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        notes_text = scrolledtext.ScrolledText(notes_frame, wrap=tk.WORD, height=8)
        notes_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        notes_text.insert(tk.END, update_info.get("release_notes", "无更新说明"))
        notes_text.config(state=tk.DISABLED)
        
        # 按钮框架
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        # 下载按钮
        download_btn = ttk.Button(
            btn_frame, 
            text="立即更新", 
            command=lambda: start_update(update_info, dialog),
            width=15
        )
        download_btn.pack(side=tk.LEFT, padx=5)
        
        # 稍后按钮
        later_btn = ttk.Button(
            btn_frame, 
            text="稍后提醒", 
            command=dialog.destroy,
            width=15
        )
        later_btn.pack(side=tk.RIGHT, padx=5)
        
        # 手动下载按钮
        manual_btn = ttk.Button(
            btn_frame, 
            text="手动下载", 
            command=lambda: webbrowser.open(update_info["download_url"]),
            width=15
        )
        manual_btn.pack(side=tk.RIGHT, padx=5)
        
        logger.info("更新对话框显示成功")
        return dialog
        
    except Exception as e:
        logger.error(f"显示更新对话框失败: {str(e)}", exc_info=True)
        messagebox.showerror("错误", f"无法显示更新对话框: {str(e)}")
def resource_path(relative_path):
    """获取资源的绝对路径，支持开发环境和PyInstaller打包环境"""
    try:
        # PyInstaller创建的临时文件夹
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)
def create_silence(duration_ms, output_file, sample_rate=44100):
    if duration_ms <= 0:
        return  # 跳过创建0ms的静音文件
    
    duration_sec = duration_ms / 1000.0
    subprocess.run([
        'ffmpeg', '-y', '-f', 'lavfi', '-i', f'anullsrc=r={sample_rate}:cl=stereo',
        '-t', str(duration_sec), '-c:a', 'libvorbis', output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def process_audio(input_file, offset, duration_ms, output_file, sample_rate=44100):
    temp_dir = tempfile.mkdtemp()
    try:
        if offset != 0:
            offset_sec = abs(offset) / 1000.0
            if offset > 0:
                silence = os.path.join(temp_dir, "silence.ogg")
                create_silence(offset, silence, sample_rate)
                temp1 = os.path.join(temp_dir, "offset.ogg")
                subprocess.run([
                    'ffmpeg', '-y', '-i', silence, '-i', input_file,
                    '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1', 
                    '-c:a', 'libvorbis', temp1
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            else:
                temp1 = os.path.join(temp_dir, "offset.ogg")
                subprocess.run([
                    'ffmpeg', '-y', '-ss', str(offset_sec), '-i', input_file,
                    '-c:a', 'copy', temp1
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        else:
            temp1 = input_file
        duration_sec = duration_ms / 1000.0
        subprocess.run([
            'ffmpeg', '-y', '-i', temp1, 
            '-t', str(duration_sec),
            '-c:a', 'libvorbis', 
            '-avoid_negative_ts', 'make_zero',
            output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    finally:
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

def outputmixogg(audio_paths, params_list, rest_ms, output_file="mix.ogg"):
    temp_dir = tempfile.mkdtemp()
    try:
        processed_files = []
        for i, (audio, params) in enumerate(zip(audio_paths, params_list)):
            bpm = params['bpm']
            offset = params['offset']
            beats = params['beats']
            duration_ms = (beats / bpm) * 60 * 1000
            output = os.path.join(temp_dir, f"processed_{i}.ogg")
            process_audio(audio, offset, duration_ms, output)
            processed_files.append(output)
        # 仅在休息时间大于0时创建休息音频
        rest_audio = None
        if rest_ms > 0:
            rest_audio = os.path.join(temp_dir, "rest.ogg")
            create_silence(rest_ms, rest_audio)
        concat_list = []
        for i, file in enumerate(processed_files):
            concat_list.append(file)
            # 只在有休息音频且不是最后一个文件时添加休息音频
            if rest_audio and i < len(processed_files) - 1:
                concat_list.append(rest_audio)
        filter_chain = []
        inputs = []
        for idx, file in enumerate(concat_list):
            inputs.extend(['-i', file])
            filter_chain.append(f'[{idx}:a]')
        filter_complex = ''.join(filter_chain) + f'concat=n={len(concat_list)}:v=0:a=1[outa]'
        subprocess.run([
            'ffmpeg', '-y',
            *inputs,
            '-filter_complex', filter_complex,
            '-map', '[outa]',
            '-c:a', 'libvorbis',
            '-fflags', '+genpts',
            output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    finally:
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

def getFileName(path):
    mc_paths = []
    for f in os.listdir(path):
        if f.lower().endswith('.mc'):
            mc_paths.append(f)
    def extract_number(filename):
        base = os.path.splitext(filename)[0]
        match = re.search(r'(\d+)', base)
        return int(match.group(1)) if match else 0
    mc_paths.sort(key=extract_number)
    return mc_paths
def update_process_list(text):
    """安全更新处理列表文本框"""
    process_list.config(state=tk.NORMAL)
    process_list.insert(tk.END, text)
    process_list.see(tk.END)
    process_list.config(state=tk.DISABLED)
    process_list.update_idletasks()  # 确保界面刷新
def process_files():
    rest = rest_var.get()
    beatrest = beatrest_var.get()
    re_gen = re_gen_var.get()
    title = title_entry.get()
    artist = artist_entry.get()
    directory = directory_var.get()
    titleorgv = titleorg_entry.get()
    artistorgv=artistorg_entry.get()
    version=version_entry.get()
    editor=editor_entry.get()
    scrollspeed=scrollspeed_var.get()
    
    if not title or not artist:
        messagebox.showerror("错误", "歌曲标题和艺术家不能为空")
        return
    
    try:
        rest = int(rest)
        beatrest = int(beatrest)
    except ValueError:
        messagebox.showerror("错误", "间隔时间和间隔小节必须是数字")
        return
    
    # 清空处理列表
    process_list.config(state=tk.NORMAL)
    process_list.delete(1.0, tk.END)
    process_list.insert(tk.END, "正在处理文件...\n")
    process_list.insert(tk.END, "="*50 + "\n")
    process_list.config(state=tk.DISABLED)
    
    # 禁用处理按钮
    process_btn.config(state=tk.DISABLED)
    
    # 在新线程中处理文件
    threading.Thread(target=process_files_thread, args=(rest, beatrest, re_gen, title, artist, directory,titleorgv,artistorgv,version,editor,scrollspeed)).start()
def transform_list(input_list):
    return [sublist[0] if sublist else {} for sublist in input_list]

def process_files_thread(rest, beatrest, re_gen, title, artist, directory,titleorgv,artistorgv,version,editor,scrollspeed):
    os.chdir(directory)
    mc_paths = getFileName(".")
    audio_paths = []
    params_list = []
    mixnote = []
    b = 0
    b1 = 0
    newtime = []
    effect = []
    blist = []
    
    # 处理每个MC文件
    for mc in mc_paths:
        with open(mc, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 获取并显示文件名和标题
        file_name = os.path.basename(mc)
        titleorg = data["meta"]["song"].get("titleorg", "无标题")
        artistorg = data["meta"]["song"].get("artistorg", "未知艺术家")
        
        # 更新处理列表
        update_process_list(f"处理文件: {file_name}\n")
        update_process_list(f"  标题: {titleorg}\n")
        update_process_list(f"  艺术家: {artistorg}\n")
        update_process_list("-"*50 + "\n")
        
        audio_paths.append(data["note"][-1]["sound"])
        last_beat = data["note"][-2]["beat"][0] if len(data["note"]) >= 2 else 0
        for i in data["note"]:
            if "endbeat" in i:
                if last_beat < i["endbeat"][0]:
                    last_beat = i["endbeat"][0]
        last_beat += beatrest
        params_list.append({
            "bpm": data["time"][0]["bpm"],
            "offset": data["note"][-1]["offset"],
            "beats": last_beat
        })
        b1 = b + last_beat
        blist.append(b)
        newtime.append([{
            "beat": [b, 0, 1],
            "bpm": data["time"][0]["bpm"],
            "delay": data["note"][-1]["offset"] if b == 0 else rest
        }]+[{"beat": [b+i["beat"][0]-data["time"][0]["beat"][0], 0, 1],
            "bpm": i["bpm"],
            "delay": i["delay"]}for i in data["time"] if i["beat"][0] != data["time"][0]["beat"][0]])
        for n in data["note"][:-1]:
            if "endbeat" in n:
                mixnote.append({
                    "beat": [n["beat"][0] + b, n["beat"][1], n["beat"][2]],
                    "column": n["column"],
                    "endbeat": [n["endbeat"][0] + b, n["endbeat"][1], n["endbeat"][2]]
                })
            else:
                mixnote.append({
                    "beat": [n["beat"][0] + b, n["beat"][1], n["beat"][2]],
                    "column": n["column"]
                })
        b = b1
    newtime=transform_list(newtime)
    for i in range(0, len(blist)):
        effect.append({
            "beat": [blist[i], 0, 1],
            "scroll": 180.0 / params_list[i]["bpm"]*float(scrollspeed)
        })
    
    # 处理音频
    process_list.insert(tk.END, "正在生成混合音频...\n")
    process_list.update_idletasks()
    if not os.path.exists("./output"):
        os.makedirs("./output")
    if os.path.exists(f"mix_{version}.ogg"):
        if re_gen:
            os.remove(f"mix_{version}.ogg")
            outputmixogg(audio_paths, params_list, rest, f"output/mix_{version}.ogg")
            process_list.insert(tk.END, f"已重新生成混合音频文件: mix_{version}.ogg\n")
    else:
        outputmixogg(audio_paths, params_list, rest, f"output/mix_{version}.ogg")
        process_list.insert(tk.END, f"已生成混合音频文件: mix_{version}.ogg\n")
    
    # 创建混合JSON
    update_process_list("正在创建谱面文件...\n")
    process_list.update_idletasks()
    
    mixjson = {
        "meta": {
            "id": 0,
            "creator": editor,
            "version": version,
            "mode": 0,
            "song": {
                "title": title,
                "artist": artist,
                "titleorg": titleorgv,
                "artistorg": artistorgv,
                "file": f"mix_{version}.ogg",
                "bpm": max([i["bpm"] for i in params_list])
            },
            "mode_ext": {
                "column": 4,
                "bar_begin": 0
            },
            "aimode": ""
        },
        "effect": effect,
        "time": newtime,
        "note": mixnote + [{
            "beat": [0, 0, 1],
            "type": 1,
            "sound": f"mix_{version}.ogg"
        }]
    }
    output_path = os.path.join(directory, "output", f"mix_{version}.mc")
    with open(output_path, 'w', encoding='utf-8') as f1:
        json.dump(mixjson, f1, indent=2, ensure_ascii=False)
    
    process_list.insert(tk.END, "="*50 + "\n")
    process_list.insert(tk.END, f"处理完成！输出文件: {output_path}\n")
    process_list.see(tk.END)
    
    # 启用处理按钮
    process_btn.config(state=tk.NORMAL)
    messagebox.showinfo("完成", f"处理完成！输出文件在: {output_path}")

def select_directory():
    dir_path = filedialog.askdirectory()
    if dir_path:
        directory_var.set(dir_path)

# 检查ffmpeg是否可用
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL,
                      check=True)
        return True
    except:
        return False
# 解决高DPI字体模糊问题
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# 创建主窗口
root = tk.Tk()
root.configure(bg="#F2F3F9")  # 添加这行，使用浅灰色调
# 创建样式并配置背景色
style = ttk.Style()
style.configure('TFrame', background='#F2F3F9')  # 纯白背景
style.configure('TLabelframe', background='#F2F3F9')
style.configure('TLabelframe.Label', background='#F2F3F9')
style.configure('TLabel', background='#F2F3F9')
style.configure('TButton', background="#F2F3F9")  # 按钮稍暗一点
style.configure('TEntry', background='#F2F3F9')  # 输入框背景
style.configure('TCheckbutton', background='#F2F3F9')  # 复选框背景
# 设置现代主题（放在创建主窗口后，创建控件前）
style = ttk.Style()
available_themes = style.theme_names()

# 优先使用vista，不可用时使用其他现代主题
if "vista" in available_themes:
    style.theme_use("vista")
elif "winnative" in available_themes:
    style.theme_use("winnative")
elif "alt" in available_themes:
    style.theme_use("alt")
else:
    style.theme_use("clam")  # 跨平台现代主题

# 解决高DPI字体模糊问题（保持原代码）
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

default_font = ("Microsoft YaHei", 10)  # 或使用 "Segoe UI" 在Windows上
root.option_add("*Font", default_font)


root.title(f"MCZ合谱工具v{CURRENT_VERSION}@CrinoBaka")
root.geometry("900x750")
try:
    root.iconbitmap(resource_path("asd.ico"))
except:
    pass  # 如果图标文件不存在则忽略
def download_ffmpeg(url, save_path):
    try:
        urllib.request.urlretrieve(url, save_path)
        return True
    except Exception as e:
        messagebox.showerror("下载错误", f"下载ffmpeg失败: {str(e)}")
        return False
if not check_ffmpeg():
    # 定义ffmpeg下载URL
    furl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "ffmpeg.zip")
    exe_path = os.path.join(os.getcwd(), "ffmpeg.exe")
    
    # 尝试下载
    if download_ffmpeg(furl, zip_path):
        try:
            # 解压zip文件
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 在zip文件中查找ffmpeg.exe
                for file in zip_ref.namelist():
                    if file.endswith("ffmpeg.exe"):
                        # 提取到当前目录
                        with open(exe_path, 'wb') as f:
                            f.write(zip_ref.read(file))
                        break
            
            # 添加当前目录到PATH
            os.environ["PATH"] = os.getcwd() + os.pathsep + os.environ["PATH"]
            
            # 再次检查是否安装成功
            if not check_ffmpeg():
                messagebox.showerror("错误", "自动安装ffmpeg失败，请手动安装并添加到系统PATH")
                sys.exit(1)
                
            messagebox.showinfo("成功", "ffmpeg已自动下载并安装到当前目录")
        except Exception as e:
            messagebox.showerror("错误", f"解压ffmpeg失败: {str(e)}")
            sys.exit(1)
        finally:
            # 清理临时文件
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
    else:
        sys.exit(1)
# 创建变量
rest_var = tk.StringVar(value="5000")
beatrest_var = tk.StringVar(value="1")
scrollspeed_var = tk.StringVar(value="1")
re_gen_var = tk.BooleanVar(value=True)
directory_var = tk.StringVar(value=os.getcwd())
title_var = tk.StringVar()
artist_var = tk.StringVar()
titleorg_var = tk.StringVar(value="MixTool")
artistorg_var = tk.StringVar(value="Various Artists")
version_var = tk.StringVar(value="4K - CrinoBaka Lv.999")
editor_var = tk.StringVar(value="CrinoBaka")

# 创建界面控件
frame = ttk.Frame(root, padding="10")
frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
frame.configure(style='TFrame')  # 添加这行

# 目录选择部分
dir_frame = ttk.LabelFrame(frame, text="工作目录", padding="10")
dir_frame.pack(fill=tk.X, pady=5)

ttk.Label(dir_frame, text="工作目录:").grid(row=0, column=0, sticky=tk.W, pady=5)
ttk.Entry(dir_frame, textvariable=directory_var, width=60).grid(row=0, column=1, padx=5)
ttk.Button(dir_frame, text="浏览", command=select_directory).grid(row=0, column=2)

# 参数设置部分
param_frame = ttk.LabelFrame(frame, text="合成参数", padding="10")
param_frame.pack(fill=tk.X, pady=5)

ttk.Label(param_frame, text="间隔时间(ms):").grid(row=0, column=0, sticky=tk.W, pady=5)
ttk.Entry(param_frame, textvariable=rest_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)

ttk.Label(param_frame, text="间隔小节:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(20,0))
ttk.Entry(param_frame, textvariable=beatrest_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=5)

ttk.Label(param_frame, text="基础流速(与const比值):").grid(row=1, column=0, sticky=tk.W, pady=5)
ttk.Entry(param_frame, textvariable=scrollspeed_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)

ttk.Checkbutton(param_frame, text="重新生成音频文件", variable=re_gen_var).grid(
    row=1, column=2, sticky=tk.W, padx=(20,0))

# 歌曲信息部分
song_frame = ttk.LabelFrame(frame, text="歌曲信息", padding="10")
song_frame.pack(fill=tk.X, pady=5)

ttk.Label(song_frame, text="歌曲标题(英文):").grid(row=0, column=0, sticky=tk.W, pady=5)
title_entry = ttk.Entry(song_frame, textvariable=title_var, width=40)
title_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

ttk.Label(song_frame, text="艺术家(英文):").grid(row=1, column=0, sticky=tk.W, pady=5)
artist_entry = ttk.Entry(song_frame, textvariable=artist_var, width=40)
artist_entry.grid(row=1, column=1, sticky=tk.W, padx=5)
ttk.Label(song_frame, text="歌曲标题(原文):").grid(row=2, column=0, sticky=tk.W, pady=5)
titleorg_entry = ttk.Entry(song_frame, textvariable=titleorg_var, width=40)
titleorg_entry.grid(row=2, column=1, sticky=tk.W, padx=5)

ttk.Label(song_frame, text="艺术家(原文):").grid(row=3, column=0, sticky=tk.W, pady=5)
artistorg_entry = ttk.Entry(song_frame, textvariable=artistorg_var, width=40)
artistorg_entry.grid(row=3, column=1, sticky=tk.W, padx=5)
ttk.Label(song_frame, text="难度版本(version):").grid(row=4, column=0, sticky=tk.W, pady=5)
version_entry = ttk.Entry(song_frame, textvariable=version_var, width=40)
version_entry.grid(row=4, column=1, sticky=tk.W, padx=5)

ttk.Label(song_frame, text="谱面作者(Editor):").grid(row=5, column=0, sticky=tk.W, pady=5)
editor_entry = ttk.Entry(song_frame, textvariable=editor_var, width=40)
editor_entry.grid(row=5, column=1, sticky=tk.W, padx=5)
# 创建正方形大按钮放在右侧
btn_frame = ttk.Frame(song_frame)
btn_frame.grid(row=0, column=2, rowspan=2, padx=20, pady=5, sticky=tk.NSEW)

# 创建正方形按钮 - 使用固定大小使其成为正方形
process_btn = ttk.Button(
    btn_frame, 
    text="开始处理", 
    command=process_files,
    width=25  ,# 增加宽度
    
)
process_btn.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# 处理列表显示部分
list_frame = ttk.LabelFrame(frame, text="处理进度", padding="10")
list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

process_list = scrolledtext.ScrolledText(list_frame, width=90, height=20)
process_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
process_list.insert(tk.END, "等待处理...\n")
process_list.config(state=tk.DISABLED)

check_updates_on_start()

# 运行主循环
root.mainloop()
