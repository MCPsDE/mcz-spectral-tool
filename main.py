import json
import re
import shutil
import subprocess
import os
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk, filedialog, scrolledtext
import threading
import tkinter.ttk as ttk
import webbrowser
from packaging import version
import requests
#pyinstaller -F -w -i asd.ico --add-data "asd.ico;." 合谱工具GUI.py
# 当前版本号 - 每次发布新版本时更新这个值
CURRENT_VERSION = "1.0.0"
import urllib
# 资源路径处理函数
# 检查更新函数
def check_for_updates():
    """检查是否有新版本可用"""
    try:
        # 从GitHub API获取最新版本信息
        response = requests.get(
            "https://gitee.com/mcpsde/mcz-spectral-tool/release/latest",
            timeout=5
        )
        response.raise_for_status()
        release_info = response.json()
        
        # 提取最新版本号
        latest_version = release_info["tag_name"].lstrip('v')
        
        # 比较版本
        if version.parse(latest_version) > version.parse(CURRENT_VERSION):
            return {
                "available": True,
                "version": latest_version,
                "download_url": release_info["assets"][0]["browser_download_url"],
                "release_notes": release_info["body"]
            }
    except Exception as e:
        print(f"检查更新失败: {str(e)}")
    
    return {"available": False}

def show_update_dialog(update_info):
    """显示更新对话框"""
    dialog = tk.Toplevel(root)
    dialog.title("发现新版本")
    dialog.geometry("500x300")
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
    notes_frame.pack(fill=tk.BOTH, expand=True, pady=10)
    
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

def start_update(update_info, dialog):
    """开始更新过程"""
    dialog.destroy()
    
    # 创建更新进度窗口
    update_dialog = tk.Toplevel(root)
    update_dialog.title("正在更新")
    update_dialog.geometry("400x200")
    update_dialog.transient(root)
    update_dialog.grab_set()
    
    # 设置窗口图标
    try:
        update_dialog.iconbitmap(resource_path("asd.ico"))
    except:
        pass
    
    # 创建框架
    frame = ttk.Frame(update_dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # 状态标签
    status_label = ttk.Label(
        frame, 
        text="正在下载更新...",
        font=("Arial", 10)
    )
    status_label.pack(pady=10)
    
    # 进度条
    progress = ttk.Progressbar(frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
    progress.pack(pady=10)
    
    # 百分比标签
    percent_label = ttk.Label(frame, text="0%")
    percent_label.pack()
    
    # 按钮框架
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=10)
    
    cancel_btn = ttk.Button(btn_frame, text="取消", command=update_dialog.destroy)
    cancel_btn.pack()
    
    # 在新线程中执行更新
    threading.Thread(
        target=perform_update, 
        args=(update_info, status_label, progress, percent_label, update_dialog),
        daemon=True
    ).start()

def perform_update(update_info, status_label, progress, percent_label, dialog):
    """执行更新过程"""
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "update.zip")
        
        # 下载更新
        response = requests.get(update_info["download_url"], stream=True)
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kibibyte
        downloaded = 0
        
        with open(zip_path, 'wb') as f:
            for data in response.iter_content(block_size):
                f.write(data)
                downloaded += len(data)
                if total_size > 0:
                    percent = int(downloaded * 100 / total_size)
                    progress['value'] = percent
                    percent_label.config(text=f"{percent}%")
                    dialog.update()
        
        # 更新状态
        status_label.config(text="正在安装更新...")
        progress['value'] = 0
        percent_label.config(text="0%")
        dialog.update()
        
        # 解压更新
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 获取文件列表
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            
            # 创建解压目录
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            # 解压所有文件
            for i, file in enumerate(file_list):
                zip_ref.extract(file, extract_dir)
                percent = int((i + 1) * 100 / total_files)
                progress['value'] = percent
                percent_label.config(text=f"{percent}%")
                dialog.update()
        
        # 更新状态
        status_label.config(text="正在替换文件...")
        progress['value'] = 0
        percent_label.config(text="0%")
        dialog.update()
        
        # 确定当前应用程序的目录
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件所在目录
            app_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境中的脚本所在目录
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 复制文件到应用程序目录
        extracted_files = os.listdir(extract_dir)
        total_files = len(extracted_files)
        
        for i, file in enumerate(extracted_files):
            src = os.path.join(extract_dir, file)
            dst = os.path.join(app_dir, file)
            
            # 如果是目录，创建它
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            
            percent = int((i + 1) * 100 / total_files)
            progress['value'] = percent
            percent_label.config(text=f"{percent}%")
            dialog.update()
        
        # 更新完成
        status_label.config(text="更新完成！请重启应用程序")
        progress['value'] = 100
        percent_label.config(text="100%")
        
        # 添加重启按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        restart_btn = ttk.Button(
            btn_frame, 
            text="立即重启", 
            command=lambda: restart_application(app_dir)
        )
        restart_btn.pack()
        
        # 关闭取消按钮
        for widget in dialog.winfo_children():
            if isinstance(widget, ttk.Button) and widget['text'] == "取消":
                widget.destroy()
    
    except Exception as e:
        status_label.config(text=f"更新失败: {str(e)}")
        progress['value'] = 0
        percent_label.config(text="错误")
        # 添加手动下载按钮
        manual_btn = ttk.Button(
            dialog, 
            text="手动下载", 
            command=lambda: webbrowser.open(update_info["download_url"])
        )
        manual_btn.pack(pady=10)

def restart_application(app_dir):
    """重启应用程序"""
    # 获取当前可执行文件路径
    executable = sys.executable
    
    # 如果是打包后的应用
    if getattr(sys, 'frozen', False):
        # 在Windows上
        if sys.platform == 'win32':
            # 使用批处理文件重启
            bat_path = os.path.join(app_dir, "restart.bat")
            with open(bat_path, 'w') as f:
                f.write(f"@echo off\n")
                f.write(f"timeout /t 1 /nobreak >nul\n")
                f.write(f'start "" "{executable}"\n')
                f.write(f"del \"%~f0\"\n")
            
            # 启动批处理文件
            subprocess.Popen(
                ['cmd', '/c', bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
    
    # 退出当前应用
    root.quit()
    root.destroy()

# 在应用程序启动时检查更新
def check_updates_on_start():
    """应用程序启动时检查更新"""
    # 延迟检查，让主界面先显示
    root.after(2000, lambda: threading.Thread(target=check_and_show_updates, daemon=True).start())

def check_and_show_updates():
    """检查并显示更新"""
    update_info = check_for_updates()
    if update_info["available"]:
        # 在主线程中显示更新对话框
        root.after(0, lambda: show_update_dialog(update_info))
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
    threading.Thread(target=process_files_thread, args=(rest, beatrest, re_gen, title, artist, directory,titleorgv,artistorgv,version,editor)).start()


def process_files_thread(rest, beatrest, re_gen, title, artist, directory,titleorgv,artistorgv,version,editor):
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
        newtime.append({
            "beat": [b, 0, 1],
            "bpm": data["time"][0]["bpm"],
            "delay": data["note"][-1]["offset"] if b == 0 else rest
        })
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
    
    for i in range(0, len(blist)):
        effect.append({
            "beat": [blist[i], 0, 1],
            "scroll": max([i["bpm"] for i in params_list]) / params_list[i]["bpm"]
        })
    
    # 处理音频
    process_list.insert(tk.END, "正在生成混合音频...\n")
    process_list.update_idletasks()
    if not os.path.exists("./output"):
        os.makedirs("./output")
    if os.path.exists("mix.ogg"):
        if re_gen:
            os.remove("mix.ogg")
            outputmixogg(audio_paths, params_list, rest, "output/mix.ogg")
            process_list.insert(tk.END, "已重新生成混合音频文件: mix.ogg\n")
    else:
        outputmixogg(audio_paths, params_list, rest, "output/mix.ogg")
        process_list.insert(tk.END, "已生成混合音频文件: mix.ogg\n")
    
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
                "file": "mix.ogg",
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
            "sound": "mix.ogg"
        }]
    }
    output_path = os.path.join(directory, "output", "mix.mc")
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
default_font = ("Microsoft YaHei", 10)  # 或使用 "Segoe UI" 在Windows上
root.option_add("*Font", default_font)
# 设置现代主题
style = ttk.Style()
# 尝试使用更现代的主题
for theme in ['vista']:
    if theme in style.theme_names():
        style.theme_use(theme)
        break
root.title("MCZ合谱工具@CrinoBaka")
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

ttk.Checkbutton(param_frame, text="重新生成音频文件", variable=re_gen_var).grid(
    row=0, column=4, sticky=tk.W, padx=(20,0))

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