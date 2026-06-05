import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import re
import threading

class NetConfigTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows 网络路由配置工具 v1.0.1")
        self.root.geometry("900x750")
        self.root.resizable(False, False)

        # 全局变量
        self.adapters = []  # 存储全量网卡列表
        self.current_adapter = ""  # 当前选中网卡名称
        self.auto_refresh_enabled = True  # 自动刷新开关
        # RFC1918私网网段列表：(目标,掩码)
        self.private_net_list = [
            ("10.0.0.0", "255.0.0.0"),
            ("172.16.0.0", "255.240.0.0"),
            ("192.168.0.0", "255.255.0.0")
        ]

        self.create_widgets()
        self.refresh_adapters()
        # 启动后台自动刷新网卡状态（2秒一次，不卡顿）
        self.auto_refresh_adapter_status()

    # 执行cmd通用函数 GBK编码适配中文windows
    def run_cmd(self, cmd):
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, encoding="gbk", errors="replace"
            )
            return result.stdout, result.stderr
        except Exception as e:
            return "", str(e)

    # ==================== 打开网络连接 ncpa.cpl ====================
    def open_ncpa(self):
        self.log("🔗 正在打开网络连接面板(ncpa.cpl)")
        subprocess.Popen("ncpa.cpl", shell=True)

    # ==================== 获取网卡 + 连接状态（新增！○ 连通 | × 断开） ====================
    def get_adapters_with_status(self):
        adapters = []

        # PowerShell 获取 网卡名称 + 连接状态
        ps_cmd = '''powershell "Get-NetAdapter | Select-Object Name, Status | ConvertTo-Csv -NoTypeInformation"'''
        out, _ = self.run_cmd(ps_cmd)

        for line in out.splitlines():
            line = line.strip().strip('"')
            if not line or "Name" in line:
                continue

            parts = line.split('","')
            if len(parts) >= 2:
                name = parts[0].strip()
                status = parts[1].strip().lower()

                # 状态标识：Up=连通 ○  其他=断开 ×
                if status == "up":
                    display_name = f"○  {name}"
                else:
                    display_name = f"×  {name}"

                adapters.append((display_name, name))  # (显示名, 真实名)
        return adapters

    # ==================== 刷新网卡列表（带状态） ====================
    def refresh_adapters(self):
        # 记录当前选中项，避免刷新后丢失选中
        current_selection = self.adapter_combobox.get()
        
        adapter_list = self.get_adapters_with_status()
        if not adapter_list:
            self.log("❌ 未读到网卡，请确认管理员运行！")
            return

        display_names = [item[0] for item in adapter_list]
        real_names = [item[1] for item in adapter_list]

        self.adapters = real_names
        self.adapter_combobox["values"] = display_names
        
        # 保持原有选中项，无选中则默认第一个
        if current_selection in display_names:
            self.adapter_combobox.set(current_selection)
        else:
            self.adapter_combobox.current(0)
            
        self.select_adapter()

    # ==================== 自动刷新网卡连接状态（核心新增） ====================
    def auto_refresh_adapter_status(self):
        if self.auto_refresh_enabled:
            try:
                self.refresh_adapters()
            except Exception:
                pass
        # 每5秒自动刷新一次
        self.root.after(5000, self.auto_refresh_adapter_status)

    # ==================== 下拉切换网卡（自动提取真实名称） ====================
    def select_adapter(self, event=None):
        selection = self.adapter_combobox.get()
        real_name = selection[2:].strip()  # 去掉 ○ 或 ×
        self.current_adapter = real_name
        self.show_adapter_info()

    # 刷新当前网卡IP信息
    def refresh_current_ip_info(self):
        if not self.current_adapter:
            messagebox.showinfo("提示", "请先选择网卡")
            return
        self.show_adapter_info()
        self.log(f"🔃 手动刷新【{self.current_adapter}】IP配置信息完成")

    # ==================== 子网前缀 转 子网掩码 ====================
    def prefix_to_mask(self, prefix):
        try:
            prefix = int(prefix)
            if prefix <0 or prefix>32:
                return ""
            bits = '1' * prefix + '0' * (32 - prefix)
            return '.'.join([str(int(bits[i:i+8], 2)) for i in range(0, 32, 8)])
        except:
            return ""

    # ==================== 读取网卡IP/掩码/网关/DNS ====================
    def get_adapter_info(self, adapter_name):
        info = {"ip": "", "mask": "", "gateway": "", "dns": ""}
        out_netsh, _ = self.run_cmd(f'netsh interface ip show config "{adapter_name}"')
        ip_match = re.search(r"IP 地址:\s*([\d\.]+)", out_netsh)
        gw_match = re.search(r"默认网关:\s*([\d\.]+)", out_netsh)
        dns_match = re.search(r"DNS 服务器:\s*([\d\.]+)", out_netsh)

        ps_cmd = f'powershell "(Get-NetIPAddress -InterfaceAlias \'{adapter_name}\' -AddressFamily IPv4 | Where-Object {{$_.IPAddress -ne \'\'}}).PrefixLength"'
        out_ps, _ = self.run_cmd(ps_cmd)

        if ip_match:
            info["ip"] = ip_match.group(1).strip()
        pre_list = re.findall(r"\d+", out_ps)
        if pre_list:
            info["mask"] = self.prefix_to_mask(pre_list[0])
        if gw_match:
            info["gateway"] = gw_match.group(1).strip()
        if dns_match:
            info["dns"] = dns_match.group(1).strip()
        return info

    def show_adapter_info(self):
        if not self.current_adapter:
            return
        info = self.get_adapter_info(self.current_adapter)
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, info["ip"])
        self.mask_entry.delete(0, tk.END)
        self.mask_entry.insert(0, info["mask"])
        self.gw_entry.delete(0, tk.END)
        self.gw_entry.insert(0, info["gateway"])
        self.dns_entry.delete(0, tk.END)
        self.dns_entry.insert(0, info["dns"])

    # ==================== DHCP / 静态IP ====================
    def set_dhcp(self):
        if not self.current_adapter:
            messagebox.showwarning("提示", "请先选择网卡")
            return
        self.log(f"🔄 网卡[{self.current_adapter}]切换DHCP自动获取")
        cmd1 = f'netsh interface ip set address "{self.current_adapter}" dhcp'
        cmd2 = f'netsh interface ip set dns "{self.current_adapter}" dhcp'
        self.run_cmd(cmd1)
        self.run_cmd(cmd2)
        self.log("✅ DHCP配置完成")
        self.show_adapter_info()

    def set_static_ip(self):
        if not self.current_adapter:
            messagebox.showwarning("提示", "请先选择网卡")
            return
        ip = self.ip_entry.get().strip()
        mask = self.mask_entry.get().strip()
        gw = self.gw_entry.get().strip()
        dns = self.dns_entry.get().strip()
        if not (ip and mask):
            messagebox.showerror("错误", "IP和子网掩码必填！")
            return
        self.log(f"🔧 设置静态IP：{ip} 掩码:{mask} 网关:{gw} DNS:{dns}")
        if gw:
            cmd_ip = f'netsh interface ip set address "{self.current_adapter}" static {ip} {mask} {gw} 1'
        else:
            cmd_ip = f'netsh interface ip set address "{self.current_adapter}" static {ip} {mask}'
        self.run_cmd(cmd_ip)
        if dns:
            cmd_dns = f'netsh interface ip set dns "{self.current_adapter}" static {dns} primary'
            self.run_cmd(cmd_dns)
        self.log("✅ 静态IP配置成功")
        self.show_adapter_info()

    # ==================== 路由功能 ====================
    def show_route_table(self):
        self.log("   正在读取系统全路由表...")
        out, _ = self.run_cmd("route print")
        self.route_text.delete(1.0, tk.END)
        self.route_text.insert(tk.END, out)
        self.log("✅ 路由表加载完毕")

    def add_route(self):
        dest = self.dest_entry.get().strip()
        r_mask = self.route_mask_entry.get().strip()
        r_gw = self.route_gw_entry.get().strip()
        if not all([dest, r_mask, r_gw]):
            messagebox.showerror("错误", "目标、掩码、网关不能为空")
            return
        cmd = f'route add {dest} mask {r_mask} {r_gw}'
        _, err = self.run_cmd(cmd)
        if err:
            self.log(f"❌ 添加路由失败：{err}")
        else:
            self.log(f"✅ 成功添加路由 {dest}/{r_mask} -> {r_gw}")

    def add_default_route(self):
        r_gw = self.route_gw_entry.get().strip()
        if not r_gw:
            messagebox.showerror("错误", "需要填写下一跳网关")
            return
        cmd = f'route add 0.0.0.0 mask 0.0.0.0 {r_gw}'
        _, err = self.run_cmd(cmd)
        if err:
            self.log(f"❌ 默认路由添加失败：{err}")
        else:
            self.log(f"✅ 默认路由 0.0.0.0 -> {r_gw} 添加成功")

    def del_default_route(self):
        cmd = "route delete 0.0.0.0"
        _, err = self.run_cmd(cmd)
        if err:
            self.log(f"❌ 删除默认路由失败：{err}")
        else:
            self.log("✅ 全部默认路由(0.0.0.0)删除成功")

    def delete_route(self):
        dest = self.dest_entry.get().strip()
        if not dest:
            messagebox.showerror("错误", "输入需要删除的目标网段")
            return
        cmd = f'route delete {dest}'
        _, err = self.run_cmd(cmd)
        if err:
            self.log(f"❌ 删除路由{dest}失败：{err}")
        else:
            self.log(f"✅ 路由{dest}已删除")

    def add_all_private_route(self):
        gw = self.route_gw_entry.get().strip()
        if not gw:
            messagebox.showerror("错误", "需要填写下一跳网关！")
            return
        self.log(f"🚀 开始批量添加三段私网路由，下一跳：{gw}")
        success_cnt = 0
        for dest, mask in self.private_net_list:
            cmd = f"route add {dest} mask {mask} {gw}"
            out, err = self.run_cmd(cmd)
            if not err:
                success_cnt += 1
                self.log(f"✅ {dest}/{mask} -> {gw} 添加成功")
            else:
                self.log(f"❌ {dest}/{mask} 添加失败:{err}")
        self.log(f"📌 私网路由添加完成：成功{success_cnt}条，总共{len(self.private_net_list)}条")

    def del_all_private_route(self):
        self.log(f"🗑️ 开始批量删除三段私网路由")
        success_cnt = 0
        for dest, mask in self.private_net_list:
            cmd = f"route delete {dest}"
            out, err = self.run_cmd(cmd)
            if not err:
                success_cnt += 1
                self.log(f"✅ {dest} 路由删除成功")
            else:
                self.log(f"❌ {dest} 删除失败:{err}")
        self.log(f"📌 私网路由删除完成：成功{success_cnt}条，总共{len(self.private_net_list)}条")

    # 日志输出
    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.update_idletasks()

    # ==================== 界面布局 ====================
    def create_widgets(self):
        # 顶部网卡选择
        top_frame = ttk.LabelFrame(self.root, text="网卡选择（自动实时刷新连接状态）")
        top_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(top_frame, text="全部网卡列表：").grid(row=0, column=0, padx=5, pady=5)
        self.adapter_combobox = ttk.Combobox(top_frame, state="readonly", width=45)
        self.adapter_combobox.grid(row=0, column=1, padx=5, pady=5)
        self.adapter_combobox.bind("<<ComboboxSelected>>", self.select_adapter)
        ttk.Button(top_frame, text="刷新网卡列表", command=self.refresh_adapters).grid(row=0, column=2, padx=5, pady=5)

        # 左侧IP配置区
        left_frame = ttk.LabelFrame(self.root, text="IPv4配置（默认填充当前网卡信息）")
        left_frame.place(x=10, y=80, width=420, height=250)
        ttk.Label(left_frame, text="IP地址：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ttk.Entry(left_frame, width=22)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(left_frame, text="子网掩码：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.mask_entry = ttk.Entry(left_frame, width=22)
        self.mask_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(left_frame, text="网关：").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.gw_entry = ttk.Entry(left_frame, width=22)
        self.gw_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(left_frame, text="首选DNS：").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.dns_entry = ttk.Entry(left_frame, width=22)
        self.dns_entry.grid(row=3, column=1, padx=5, pady=5)

        # 按钮
        ttk.Button(left_frame, text="切换DHCP自动", command=lambda:threading.Thread(target=self.set_dhcp,daemon=True).start()).grid(row=4, column=0, padx=3, pady=10)
        ttk.Button(left_frame, text="保存静态IP", command=lambda:threading.Thread(target=self.set_static_ip,daemon=True).start()).grid(row=4, column=1, padx=3, pady=10)
        ttk.Button(left_frame, text="刷新IP信息", command=self.refresh_current_ip_info).grid(row=5, column=0, columnspan=2, padx=3, pady=2)

        # 右侧路由配置
        right_frame = ttk.LabelFrame(self.root, text="路由配置（独立功能，无需选择网卡）")
        right_frame.place(x=450, y=80, width=420, height=280)
        ttk.Label(right_frame, text="目标网段：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.dest_entry = ttk.Entry(right_frame, width=22)
        self.dest_entry.grid(row=0, column=1, padx=5, pady=5)
        self.dest_entry.insert(0,"0.0.0.0")

        ttk.Label(right_frame, text="路由掩码：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.route_mask_entry = ttk.Entry(right_frame, width=22)
        self.route_mask_entry.grid(row=1, column=1, padx=5, pady=5)
        self.route_mask_entry.insert(0,"0.0.0.0")

        ttk.Label(right_frame, text="下一跳网关：").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.route_gw_entry = ttk.Entry(right_frame, width=22)
        self.route_gw_entry.grid(row=2, column=1, padx=5, pady=5)

        # 第1行
        ttk.Button(right_frame, text="添加默认路由", command=lambda:threading.Thread(target=self.add_default_route,daemon=True).start()).grid(row=3, column=0, padx=3, pady=5)
        ttk.Button(right_frame, text="删除默认路由", command=lambda:threading.Thread(target=self.del_default_route,daemon=True).start()).grid(row=3, column=1, padx=3, pady=5)

        # 第2行
        ttk.Button(right_frame, text="添加目标路由", command=lambda:threading.Thread(target=self.add_route,daemon=True).start()).grid(row=4, column=0, padx=3, pady=5)
        ttk.Button(right_frame, text="删除目标路由", command=lambda:threading.Thread(target=self.delete_route,daemon=True).start()).grid(row=4, column=1, padx=3, pady=5)

        # 第3行
        ttk.Button(right_frame, text="添加私网路由", command=lambda:threading.Thread(target=self.add_all_private_route,daemon=True).start()).grid(row=5, column=0, padx=3, pady=5)
        ttk.Button(right_frame, text="删除私网路由", command=lambda:threading.Thread(target=self.del_all_private_route,daemon=True).start()).grid(row=5, column=1, padx=3, pady=5)

        # 第4行
        ttk.Button(right_frame, text="查看全部路由", command=lambda:threading.Thread(target=self.show_route_table,daemon=True).start()).grid(row=6, column=0, padx=3, pady=8)
        ttk.Button(right_frame, text="打开网络连接", command=self.open_ncpa).grid(row=6, column=1, padx=3, pady=8)

        # 路由表
        route_frame = ttk.LabelFrame(self.root, text="系统完整路由表")
        route_frame.place(x=10, y=370, width=860, height=180)
        self.route_text = scrolledtext.ScrolledText(route_frame)
        self.route_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 日志
        log_frame = ttk.LabelFrame(self.root, text="运行操作日志")
        log_frame.place(x=10, y=560, width=860, height=150)
        self.log_text = scrolledtext.ScrolledText(log_frame)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = NetConfigTool(root)
    root.mainloop()