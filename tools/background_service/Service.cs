// Windows service for the legacy winws engine. No shell, script execution or
// caller-selected executables. Keep the protocol and option allowlist explicit.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.ServiceProcess;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using Microsoft.Win32.SafeHandles;
using Microsoft.Win32;

[assembly: AssemblyTitle("Zapret GUI Background Service")]
[assembly: AssemblyVersion("1.0.0.0")]

public sealed class Argument
{
    public string name;
    public string value;
    public int file = -1;
    public string prefix;
}
public sealed class Request
{
    public string op;
    public Argument[] args;
    public string[] files;
}

public static class Options
{
    // These options only consume values. Never admit new engine options by
    // prefix: a future --lua-init/--pidfile must not become a SYSTEM primitive.
    static readonly HashSet<string> Values = new HashSet<string>((
        "comment ctrack-timeouts ctrack-disable ipcache-lifetime ipcache-hostname " +
        "wf-iface wf-l3 wf-tcp wf-udp wf-filter-lan ssid-filter nlm-filter " +
        "new skip filter-l3 filter-tcp filter-udp filter-l7 ipset-ip ipset-exclude-ip " +
        "hostlist-domains hostlist-exclude-domains hostlist-auto-fail-threshold " +
        "hostlist-auto-fail-time hostlist-auto-retrans-threshold " +
        "wsize wssize wssize-cutoff wssize-forced-cutoff synack-split " +
        "orig-ttl orig-ttl6 orig-autottl orig-autottl6 orig-tcp-flags-set orig-tcp-flags-unset " +
        "orig-mod-start orig-mod-cutoff dup dup-replace dup-ttl dup-ttl6 dup-autottl dup-autottl6 " +
        "dup-tcp-flags-set dup-tcp-flags-unset dup-fooling dup-ts-increment dup-badseq-increment " +
        "dup-badack-increment dup-ip-id dup-start dup-cutoff hostcase hostspell hostnospace " +
        "domcase methodeol ip-id dpi-desync dpi-desync-ttl dpi-desync-ttl6 dpi-desync-autottl " +
        "dpi-desync-autottl6 dpi-desync-tcp-flags-set dpi-desync-tcp-flags-unset " +
        "dpi-desync-fooling dpi-desync-repeats dpi-desync-skip-nosni dpi-desync-split-pos " +
        "dpi-desync-split-seqovl dpi-desync-fakedsplit-mod dpi-desync-hostfakesplit-midhost " +
        "dpi-desync-hostfakesplit-mod dpi-desync-ipfrag-pos-udp dpi-desync-ipfrag-pos-tcp " +
        "dpi-desync-ts-increment dpi-desync-badseq-increment dpi-desync-badack-increment " +
        "dpi-desync-any-protocol dpi-desync-fake-tcp-mod dpi-desync-fake-tls-mod " +
        "dpi-desync-udplen-increment dpi-desync-start dpi-desync-cutoff").Split(' '));
    static readonly HashSet<string> Lists = new HashSet<string>(new[] {
        "hostlist", "hostlist-exclude", "ipset", "ipset-exclude" });
    static readonly HashSet<string> Payloads = new HashSet<string>((
        "dpi-desync-split-seqovl-pattern dpi-desync-fakedsplit-pattern dpi-desync-udplen-pattern " +
        "dpi-desync-fake-http dpi-desync-fake-tls dpi-desync-fake-unknown dpi-desync-fake-syndata " +
        "dpi-desync-fake-quic dpi-desync-fake-wireguard dpi-desync-fake-dht dpi-desync-fake-discord " +
        "dpi-desync-fake-stun dpi-desync-fake-unknown-udp").Split(' '));

    public static string[] Materialize(Request request, string directory)
    {
        if (request.args == null || request.args.Length == 0 || request.args.Length > 2048)
            throw new InvalidDataException("Invalid argument count");
        string[] encoded = request.files ?? new string[0];
        if (encoded.Length > 256) throw new InvalidDataException("Too many files");
        var paths = new List<string>();
        long total = 0;
        foreach (string value in encoded)
        {
            byte[] data = Convert.FromBase64String(value);
            total += data.Length;
            if (total > 32 * 1024 * 1024) throw new InvalidDataException("Profile files exceed 32 MiB");
            string extension = data.Length > 2 && data[0] == 31 && data[1] == 139 ? ".dat.gz" : ".dat";
            string path = Path.Combine(directory, "input-" + paths.Count + extension);
            File.WriteAllBytes(path, data);
            paths.Add(path);
        }
        var output = new List<string>();
        foreach (Argument arg in request.args)
        {
            string name = arg.name ?? "";
            string value = arg.value;
            if ((value != null && (value.Length > 16000 || value.IndexOf('\0') >= 0)) ||
                !Regex.IsMatch(name, @"\A[a-z0-9-]+\z"))
                throw new InvalidDataException("Invalid option");
            bool file = arg.file >= 0;
            bool payload = Payloads.Contains(name);
            bool raw = name == "wf-raw" || name == "wf-raw-part";
            if (file)
            {
                if ((!Lists.Contains(name) && !payload && !raw) || arg.file >= paths.Count || value != null)
                    throw new InvalidDataException("Invalid file option: " + name);
                string prefix = arg.prefix ?? "";
                if (!Regex.IsMatch(prefix, @"\A(?:\+[0-9]+)?\z") || (!payload && prefix != ""))
                    throw new InvalidDataException("Invalid payload offset");
                value = prefix + (raw || prefix != "" ? "@" : "") + paths[arg.file];
            }
            else if (Lists.Contains(name))
                throw new InvalidDataException("File content required: " + name);
            else if (payload)
            {
                if (value == null || !(Regex.IsMatch(value, @"\A0x[0-9a-fA-F]+\z") ||
                    (name == "dpi-desync-fake-tls" && Regex.IsMatch(value, @"\A!(?:\+[0-9]+)?\z"))))
                    throw new InvalidDataException("Payload must be uploaded: " + name);
            }
            else if (raw)
            {
                if (String.IsNullOrEmpty(value) || value.StartsWith("@"))
                    throw new InvalidDataException("Raw filter file must be uploaded");
            }
            else if (name == "debug")
            {
                if (value != "0" && value != "1") throw new InvalidDataException("File logging is not supported");
            }
            else if (!Values.Contains(name))
                throw new InvalidDataException("Unsupported background option: --" + name);
            output.Add("--" + name + (value == null ? "" : "=" + value));
        }
        return output.ToArray();
    }
}

public static class TelegramHosts
{
    public static void SetEnabled(bool enabled)
    {
        string path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"drivers\etc\hosts");
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
            throw new IOException("The system hosts file must not be a link");
        // FileShare.Read serializes this with other writers without replacing the
        // hosts ACL or allowing the IPC caller to choose a privileged file.
        using (var file = new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.Read)) {
            string original;
            using (var reader = new StreamReader(file, Encoding.UTF8, true, 4096, true)) original = reader.ReadToEnd();
            string updated = original.Replace("\r\n", "\n").Replace("\r", "\n");
            updated = Regex.Replace(updated, @"(?ms)^# ZapretGUI (?:Flowseal )?Telegram Web hosts begin\n.*?^# ZapretGUI (?:Flowseal )?Telegram Web hosts end(?:\n|$)", "").TrimEnd();
            if (updated != "") updated += "\n";
            if (enabled) {
                string entries;
                using (var reader = new StreamReader(Assembly.GetExecutingAssembly().GetManifestResourceStream("TelegramHosts")))
                    entries = reader.ReadToEnd();
                updated += "# ZapretGUI Flowseal Telegram Web hosts begin\n" +
                    "# Telegram Web hosts from Flowseal/zapret-discord-youtube .service/hosts\n" + entries +
                    "# ZapretGUI Flowseal Telegram Web hosts end\n";
            }
            if (updated != original) {
                byte[] data = new UTF8Encoding(false).GetBytes(updated);
                file.Position = 0; file.Write(data, 0, data.Length); file.SetLength(data.Length); file.Flush(true);
            }
        }
        Native.DnsFlushResolverCache();
    }
}

public sealed class Child : IDisposable
{
    IntPtr process, job;
    public uint Pid { get; private set; }
    readonly StringBuilder log = new StringBuilder();
    public string Log { get { lock (log) return log.ToString(); } }
    public bool Running { get { return process != IntPtr.Zero && Native.WaitForSingleObject(process, 0) == 258; } }
    public uint ExitCode { get { uint code; Native.Check(Native.GetExitCodeProcess(process, out code)); return code; } }
    public bool Wait(uint milliseconds) { return Native.WaitForSingleObject(process, milliseconds) == 0; }

    public Child(string executable, string[] arguments)
    {
        IntPtr read = IntPtr.Zero, write = IntPtr.Zero, input = IntPtr.Zero;
        Native.PROCESS_INFORMATION pi = new Native.PROCESS_INFORMATION();
        try
        {
            job = Native.CreateJobObject(IntPtr.Zero, null);
            Native.Check(job != IntPtr.Zero);
            var limit = new Native.JOB_EXTENDED_LIMIT();
            limit.BasicLimitInformation.LimitFlags = 0x2000; // KILL_ON_JOB_CLOSE
            Native.Check(Native.SetInformationJobObject(job, 9, ref limit, (uint)Marshal.SizeOf(limit)));
            var sa = new Native.SECURITY_ATTRIBUTES();
            sa.nLength = Marshal.SizeOf(sa); sa.bInheritHandle = true;
            Native.Check(Native.CreatePipe(out read, out write, ref sa, 0));
            Native.Check(Native.SetHandleInformation(read, 1, 0));
            input = Native.CreateFile("NUL", 0x80000000, 3, ref sa, 3, 0, IntPtr.Zero);
            Native.Check(input != new IntPtr(-1));
            var si = new Native.STARTUPINFO();
            si.cb = Marshal.SizeOf(si); si.dwFlags = 0x101; // USESTDHANDLES | USESHOWWINDOW
            si.wShowWindow = Native.SW_HIDE;
            si.hStdInput = input; si.hStdOutput = write; si.hStdError = write;
            string command = Native.Quote(executable);
            foreach (string arg in arguments) command += " " + Native.Quote(arg);
            if (command.Length >= 32767) throw new InvalidDataException("winws command exceeds Windows limit");
            Native.Check(Native.CreateProcess(executable, new StringBuilder(command), IntPtr.Zero,
                IntPtr.Zero, true, Native.CREATE_NO_WINDOW | Native.CREATE_SUSPENDED,
                IntPtr.Zero, Path.GetDirectoryName(executable), ref si, out pi));
            process = pi.hProcess; Pid = pi.dwProcessId;
            // Fail closed: the child has not executed a single instruction yet.
            Native.Check(Native.AssignProcessToJobObject(job, process));
            var stream = new FileStream(new SafeFileHandle(read, true), FileAccess.Read, 4096, false);
            read = IntPtr.Zero;
            var reader = new Thread(delegate() {
                try { using (stream) using (var text = new StreamReader(stream, Encoding.UTF8)) {
                    char[] buffer = new char[2048]; int count;
                    while ((count = text.Read(buffer, 0, buffer.Length)) > 0) lock (log) {
                        log.Append(buffer, 0, count);
                        if (log.Length > 16000) log.Remove(0, log.Length - 16000);
                    }
                }} catch (IOException) { }
            });
            reader.IsBackground = true; reader.Start();
            Native.Check(Native.ResumeThread(pi.hThread) != 0xffffffff);
        }
        catch
        {
            if (process != IntPtr.Zero) { Native.TerminateProcess(process, 1); Native.WaitForSingleObject(process, 10000); }
            Dispose(); throw;
        }
        finally
        {
            Native.Close(pi.hThread); Native.Close(read); Native.Close(write); Native.Close(input);
        }
    }
    public void Stop()
    {
        if (!Running) return;
        Native.Check(Native.TerminateJobObject(job, 1));
        if (Native.WaitForSingleObject(process, 10000) != 0) throw new IOException("winws did not stop within 10 seconds");
    }
    public void Dispose()
    {
        Native.Close(job); job = IntPtr.Zero;
        if (process != IntPtr.Zero) Native.WaitForSingleObject(process, 10000);
        Native.Close(process); process = IntPtr.Zero;
    }
}

public sealed class Broker : ServiceBase
{
    public const int Protocol = 1;
    readonly string sid, root, pipeName;
    volatile bool quitting;
    NamedPipeServerStream pipe;
    readonly object gate = new object();
    Child child;
    string runDirectory;
    public Broker(string userSid, string directory, string testPipe = null)
    {
        sid = new SecurityIdentifier(userSid).Value;
        root = directory;
        ServiceName = Install.ServiceName(sid);
        pipeName = testPipe ?? ServiceName;
        CanStop = true; CanShutdown = true; AutoLog = false;
    }
    protected override void OnStart(string[] args)
    {
        var thread = new Thread(Serve); thread.IsBackground = true; thread.Start();
    }
    protected override void OnStop()
    {
        quitting = true;
        if (pipe != null) pipe.Dispose();
        lock (gate) StopChild();
    }
    protected override void OnShutdown() { OnStop(); }
    public void TestRun() { Serve(); }
    void StopChild()
    {
        // Clear the shared field first. If a broken child times out during
        // termination, no later request can mistake it for a live bypass.
        Child current = child; child = null;
        try { if (current != null) current.Stop(); }
        finally {
            if (current != null) current.Dispose(); // closing the job kills its whole tree
            if (runDirectory != null) {
                try { Directory.Delete(runDirectory, true); }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
                runDirectory = null;
            }
        }
    }
    void StopLegacy()
    {
        // Only the executable path approved during installation may be adopted.
        string file = Path.Combine(root, "legacy-path.txt");
        if (!File.Exists(file)) return;
        string expected = File.ReadAllText(file).Trim();
        foreach (string name in new[] { "zapret", "zapret_discord" })
        using (var key = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\" + name))
        {
            string command = key == null ? "" : Convert.ToString(key.GetValue("ImagePath"));
            if (!command.StartsWith(Native.Quote(expected) + " ", StringComparison.OrdinalIgnoreCase)) continue;
            using (var svc = new ServiceController(name)) {
                if (svc.Status != ServiceControllerStatus.Stopped) {
                    svc.Stop(); svc.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(10));
                }
            }
        }
        foreach (var proc in Process.GetProcessesByName("winws")) using (proc)
        {
            try {
                if (!String.Equals(proc.MainModule.FileName, expected, StringComparison.OrdinalIgnoreCase)) continue;
                proc.Kill();
                if (!proc.WaitForExit(10000)) throw new IOException("Legacy winws did not stop");
            } catch (InvalidOperationException) { } // exited between enumeration and inspection
              catch (Win32Exception) { } // an unrelated protected process
        }
    }
    object Status()
    {
        return new { ok = true, protocol = Protocol, running = child != null && child.Running,
            pid = child == null ? 0 : child.Pid, exit_code = child == null || child.Running ? (uint?)null : child.ExitCode,
            log = child == null ? "" : child.Log,
            engine = File.ReadAllText(Path.Combine(root, "engine.sha256")).Trim(),
            helper = Install.FileHash(Assembly.GetExecutingAssembly().Location) };
    }
    object Dispatch(Request request)
    {
        lock (gate)
        {
            if (quitting) throw new IOException("Service is stopping");
            if (request.op == "hello" || request.op == "status") return Status();
            if (request.op == "telegram-hosts-on" || request.op == "telegram-hosts-off") {
                TelegramHosts.SetEnabled(request.op == "telegram-hosts-on"); return Status();
            }
            if (request.op == "stop") { StopChild(); StopLegacy(); return Status(); }
            if (request.op != "start" && request.op != "validate") throw new InvalidDataException("Unknown operation");
            if (child != null && child.Running) throw new IOException("Bypass is already running");
            StopChild();
            runDirectory = Path.Combine(root, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(runDirectory);
            try
            {
                string[] args = Options.Materialize(request, runDirectory);
                if (request.op == "validate") {
                    var validationArgs = new List<string>(args); validationArgs.Insert(0, "--dry-run");
                    child = new Child(Path.Combine(root, "engine", "winws.exe"), validationArgs.ToArray());
                    if (!child.Wait(10000)) throw new IOException("Profile validation timed out");
                    Thread.Sleep(50); // let the output reader consume the final buffered bytes
                    uint code = child.ExitCode; string log = child.Log;
                    StopChild();
                    return new { ok = code == 0, error = code == 0 ? "" : log, exit_code = code, log = log };
                }
                child = new Child(Path.Combine(root, "engine", "winws.exe"), args);
                // A successful CreateProcess alone says nothing about driver initialization.
                Thread.Sleep(1200);
                if (!child.Running)
                    throw new IOException("winws exited (" + child.ExitCode + "): " + child.Log);
                return Status();
            }
            catch { StopChild(); throw; }
        }
    }
    void Serve()
    {
        while (!quitting)
        {
            try
            {
                var security = new PipeSecurity();
                security.SetAccessRuleProtection(true, false);
                security.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.NetworkSid, null), PipeAccessRights.FullControl, AccessControlType.Deny));
                security.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(sid),
                    PipeAccessRights.ReadData | PipeAccessRights.WriteData | PipeAccessRights.ReadAttributes |
                    PipeAccessRights.Synchronize, AccessControlType.Allow));
                security.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null), PipeAccessRights.FullControl, AccessControlType.Allow));
                using (pipe = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1,
                    PipeTransmissionMode.Byte, PipeOptions.Asynchronous, 65536, 65536, security))
                {
                    pipe.WaitForConnection();
                    uint pid;
                    Native.Check(Native.GetNamedPipeClientProcessId(pipe.SafePipeHandle, out pid));
                    using (Process owner = Process.GetProcessById((int)pid))
                    // Capture this connection; a queued timer callback must never
                    // dispose the next GUI's pipe after this timer is disposed.
                    {
                    var activePipe = pipe;
                    using (var watcher = new Timer(delegate(object state) {
                        try { if (owner.HasExited) activePipe.Dispose(); } catch { }
                    }, null, 500, 500))
                    {
                        // Pin the original process handle; PID reuse cannot transfer ownership.
                        IntPtr ownerHandle = owner.Handle;
                        var json = new JavaScriptSerializer { MaxJsonLength = 48 * 1024 * 1024, RecursionLimit = 16 };
                        while (!quitting)
                        {
                            byte[] header = ReadExact(pipe, 4);
                            int size = BitConverter.ToInt32(header, 0);
                            if (size <= 0 || size > 48 * 1024 * 1024) throw new InvalidDataException("Invalid message length");
                            byte[] body = ReadExact(pipe, size);
                            object reply;
                            try { reply = Dispatch(json.Deserialize<Request>(Encoding.UTF8.GetString(body))); }
                            catch (Exception ex) { reply = new { ok = false, error = ex.Message }; }
                            byte[] encoded = Encoding.UTF8.GetBytes(json.Serialize(reply));
                            pipe.Write(BitConverter.GetBytes(encoded.Length), 0, 4);
                            pipe.Write(encoded, 0, encoded.Length); pipe.Flush();
                        }
                    }
                    }
                }
            }
            catch (EndOfStreamException) { }
            catch (Exception ex) {
                if (!quitting) {
                    try { File.WriteAllText(Path.Combine(root, "service-last-error.txt"), DateTime.UtcNow.ToString("o") + "\n" + ex); } catch { }
                    Thread.Sleep(100);
                }
            }
            finally { lock (gate) { try { StopChild(); } catch { if (child != null) child.Dispose(); } } }
        }
    }
    static byte[] ReadExact(Stream stream, int size)
    {
        byte[] data = new byte[size]; int offset = 0;
        while (offset < size)
        {
            var pending = stream.BeginRead(data, offset, size - offset, null, null);
            int count;
            using (var ready = pending.AsyncWaitHandle) {
                if (!ready.WaitOne(45000)) throw new IOException("GUI connection timed out");
                count = stream.EndRead(pending);
            }
            if (count == 0) throw new EndOfStreamException();
            offset += count;
        }
        return data;
    }
}

public static class Install
{
    public static string ServiceName(string sid) { return "ZapretGUI.Bypass." + sid; }
    static readonly string[] EngineFiles = { "winws.exe", "cygwin1.dll", "WinDivert.dll", "WinDivert64.sys" };
    public static string FileHash(string path) {
        using (var hash = SHA256.Create()) using (var file = File.OpenRead(path))
            return BitConverter.ToString(hash.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
    }
    public static string Fingerprint(string directory)
    {
        using (var hash = SHA256.Create()) {
            var manifest = new StringBuilder();
            foreach (string name in EngineFiles) manifest.Append(name).Append(":").Append(
                BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(Path.Combine(directory, name)))).Replace("-", "").ToLowerInvariant()).Append("\n");
            return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(manifest.ToString()))).Replace("-", "").ToLowerInvariant();
        }
    }
    static void NoReparse(string path)
    {
        for (var dir = new DirectoryInfo(path); dir != null; dir = dir.Parent)
            if (dir.Exists && (dir.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new IOException("Service directory must not contain junctions: " + dir.FullName);
    }
    static void SecureDirectory(string path)
    {
        NoReparse(path);
        if (Directory.Exists(path)) {
            var owner = Directory.GetAccessControl(path).GetOwner(typeof(SecurityIdentifier)).Value;
            if (owner != "S-1-5-18" && owner != "S-1-5-32-544")
                throw new IOException("Untrusted service directory owner: " + path);
        }
        var acl = new DirectorySecurity();
        acl.SetAccessRuleProtection(true, false);
        acl.SetOwner(new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null));
        foreach (var sid in new[] { WellKnownSidType.LocalSystemSid, WellKnownSidType.BuiltinAdministratorsSid })
            acl.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(sid, null), FileSystemRights.FullControl,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        acl.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null), FileSystemRights.ReadAndExecute,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        if (!Directory.Exists(path)) Directory.CreateDirectory(path, acl);
        else Directory.SetAccessControl(path, acl);
    }
    static void Sc(params string[] args)
    {
        var si = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "sc.exe"));
        si.UseShellExecute = false; si.CreateNoWindow = true;
        foreach (string arg in args) si.Arguments += Native.Quote(arg) + " ";
        using (var p = Process.Start(si)) { if (!p.WaitForExit(20000)) throw new IOException("SCM timed out");
            if (p.ExitCode != 0) throw new IOException("SCM error " + p.ExitCode + " (" + args[0] + ")"); }
    }
    static void CheckTree(string directory)
    {
        NoReparse(directory);
        foreach (string child in Directory.GetDirectories(directory)) CheckTree(child);
    }
    static void CleanVersions(string userRoot, string keep)
    {
        if (!Directory.Exists(userRoot)) return;
        NoReparse(userRoot);
        foreach (string directory in Directory.GetDirectories(userRoot)) {
            if (directory == keep || !Regex.IsMatch(Path.GetFileName(directory), @"\A[0-9a-f]{32}\z")) continue;
            try { CheckTree(directory); Directory.Delete(directory, true); }
            catch (IOException) { } // a previous helper may still be finishing installation
            catch (UnauthorizedAccessException) { }
        }
    }
    public static void Run(string source, string sid, bool remove)
    {
        sid = new SecurityIdentifier(sid).Value;
        if (!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator))
            throw new UnauthorizedAccessException("Administrator approval is required to install the background service");
        string name = ServiceName(sid);
        bool exists = false;
        using (var svc = new ServiceController(name)) {
            try { var status = svc.Status; exists = true; } catch (InvalidOperationException) { }
            if (exists && svc.Status != ServiceControllerStatus.Stopped) {
                svc.Stop(); svc.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(20));
            }
        }
        string parent = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "ZapretGUI Background");
        string userRoot = Path.Combine(parent, sid);
        if (remove) {
            if (exists) Sc("delete", name);
            CleanVersions(userRoot, null);
            return;
        }
        // Immutable versioned directory: an update never overwrites a loaded EXE/DLL.
        SecureDirectory(parent);
        SecureDirectory(userRoot);
        string root = Path.Combine(userRoot, Guid.NewGuid().ToString("N")); SecureDirectory(root);
        string engine = Path.Combine(root, "engine"); SecureDirectory(engine);
        foreach (string file in EngineFiles) File.Copy(Path.Combine(source, file), Path.Combine(engine, file));
        // WinDivert32 is optional for legacy 32-bit distributions.
        if (File.Exists(Path.Combine(source, "WinDivert32.sys"))) File.Copy(Path.Combine(source, "WinDivert32.sys"), Path.Combine(engine, "WinDivert32.sys"));
        string executable = Path.Combine(root, "ZapretGUI.Service.exe");
        File.Copy(Assembly.GetExecutingAssembly().Location, executable);
        File.WriteAllText(Path.Combine(root, "engine.sha256"), Fingerprint(engine));
        File.WriteAllText(Path.Combine(root, "legacy-path.txt"), Path.GetFullPath(Path.Combine(source, "winws.exe")));
        string command = Native.Quote(executable) + " --service " + Native.Quote(sid);
        if (exists) Sc("config", name, "binPath=", command, "start=", "auto", "obj=", "LocalSystem");
        else Sc("create", name, "binPath=", command, "start=", "auto", "obj=", "LocalSystem", "DisplayName=", "Zapret GUI Background (" + sid + ")");
        Sc("description", name, "Runs the Zapret GUI bypass in the background. Stops winws when its GUI disconnects.");
        // The GUI may start/query the fixed service; never CHANGE_CONFIG or WRITE_DAC.
        Sc("sdset", name, "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;CCLCRP;;;" + sid + ")");
        // Migration: remove the old elevated GUI task. Autostart now uses HKCU Run.
        var task = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "schtasks.exe"), "/Delete /TN ZapretGUI /F");
        task.UseShellExecute = false; task.CreateNoWindow = true;
        using (var p = Process.Start(task)) p.WaitForExit(10000);
        Sc("start", name);
        CleanVersions(userRoot, root);
        // Preserve the timestamp preparation formerly performed by service.bat.
        var netsh = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "netsh.exe"),
            "interface tcp set global timestamps=enabled");
        netsh.UseShellExecute = false; netsh.CreateNoWindow = true;
        using (var p = Process.Start(netsh)) p.WaitForExit(10000);
    }
}

public static class Program
{
    public static int Main(string[] args)
    {
        try
        {
            if (args.Length == 2 && args[0] == "--service") {
                ServiceBase.Run(new Broker(args[1], AppDomain.CurrentDomain.BaseDirectory)); return 0;
            }
            if (args.Length == 3 && args[0] == "--install") { Install.Run(args[1], args[2], false); return 0; }
            if (args.Length == 2 && args[0] == "--uninstall") { Install.Run(null, args[1], true); return 0; }
            // Explicit test host: uses the caller's rights, never registers a service.
            if (args.Length == 4 && args[0] == "--test-host") {
                new Broker(args[1], Path.GetFullPath(args[2]), args[3]).TestRun(); return 0;
            }
            return 2;
        }
        catch (Exception ex)
        {
            // WinExe has no console; a small native dialog preserves installer errors.
            Native.MessageBox(IntPtr.Zero, ex.Message, "Zapret GUI Background Service", 0x10);
            return 1;
        }
    }
}

public static class Native
{
    public const uint CREATE_SUSPENDED = 0x00000004;
    public const uint CREATE_NO_WINDOW = 0x08000000;
    public const ushort SW_HIDE = 0;
    public static void Check(bool ok) { if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }
    public static void Close(IntPtr h) { if (h != IntPtr.Zero && h != new IntPtr(-1)) CloseHandle(h); }
    public static string Quote(string value) {
        return "\"" + Regex.Replace(Regex.Replace(value, "(\\\\*)\"", "$1$1\\\""), "(\\\\+)$", "$1$1") + "\"";
    }
    [StructLayout(LayoutKind.Sequential)] public struct SECURITY_ATTRIBUTES { public int nLength; public IntPtr lpSecurityDescriptor; [MarshalAs(UnmanagedType.Bool)] public bool bInheritHandle; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] public struct STARTUPINFO {
        public int cb; public string lpReserved, lpDesktop, lpTitle;
        public uint dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public ushort wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }
    [StructLayout(LayoutKind.Sequential)] public struct PROCESS_INFORMATION { public IntPtr hProcess, hThread; public uint dwProcessId, dwThreadId; }
    [StructLayout(LayoutKind.Sequential)] public struct JOB_BASIC_LIMIT {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit; public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize; public uint ActiveProcessLimit;
        public UIntPtr Affinity; public uint PriorityClass, SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)] public struct IO_COUNTERS { public ulong a, b, c, d, e, f; }
    [StructLayout(LayoutKind.Sequential)] public struct JOB_EXTENDED_LIMIT {
        public JOB_BASIC_LIMIT BasicLimitInformation; public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern bool CreateProcess(string app, StringBuilder cmd, IntPtr pa, IntPtr ta, bool inherit, uint flags, IntPtr env, string cwd, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern uint ResumeThread(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool TerminateProcess(IntPtr h, uint code);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool GetExitCodeProcess(IntPtr h, out uint code);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern IntPtr CreateJobObject(IntPtr sa, string name);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool SetInformationJobObject(IntPtr h, int cls, ref JOB_EXTENDED_LIMIT info, uint size);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool TerminateJobObject(IntPtr job, uint code);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CreatePipe(out IntPtr read, out IntPtr write, ref SECURITY_ATTRIBUTES sa, uint size);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool SetHandleInformation(IntPtr h, uint mask, uint flags);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern IntPtr CreateFile(string path, uint access, uint share, ref SECURITY_ATTRIBUTES sa, uint mode, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int MessageBox(IntPtr hwnd, string text, string title, uint type);
    [DllImport("dnsapi.dll")] public static extern bool DnsFlushResolverCache();
}
