import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../providers/monitor_provider.dart';
import '../widgets/gauge_widget.dart';
import '../widgets/process_tile.dart';
import '../widgets/alert_banner.dart';
import 'connect_screen.dart';

/// DashboardScreen — main monitoring view with gauges, stats, process list,
/// alert banners, and event log.
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final monitor = context.watch<MonitorProvider>();
    final metric = monitor.latestMetric;

    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      body: SafeArea(
        child: Column(
          children: [
            // ── Top Bar ────────────────────────────────────────────────────
            _TopBar(
              host: monitor.serverHost,
              isConnected: monitor.isConnected,
              onDisconnect: () async {
                await monitor.disconnect();
                if (context.mounted) {
                  Navigator.of(context).pushReplacement(
                    MaterialPageRoute(
                        builder: (_) => const ConnectScreen()),
                  );
                }
              },
            ),

            // ── Alert Banners ─────────────────────────────────────────────
            if (monitor.alerts.isNotEmpty)
              Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Column(
                  children: monitor.alerts
                      .asMap()
                      .entries
                      .map((e) => AlertBanner(
                            message: e.value,
                            onDismiss: () => monitor.dismissAlert(e.key),
                          ))
                      .toList(),
                ),
              ),

            // ── Body ────────────────────────────────────────────────────────────
            Expanded(
              child: _selectedIndex == 0
                  ? _LeftPanel(metric: metric, monitor: monitor)
                  : _selectedIndex == 1
                      ? _ProcessPanel(
                          monitor: monitor,
                          sortby: monitor.currentSortby,
                          onSortChange: (v) =>
                              monitor.refreshProcesses(sortby: v),
                        )
                      : _ControlPanel(monitor: monitor),
            ),
          ],
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: const Color(0xFF151A2C),
        selectedItemColor: const Color(0xFF00B4D8),
        unselectedItemColor: Colors.white38,
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() {
            _selectedIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard_rounded),
            label: 'Dashboard',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.list_alt_rounded),
            label: 'Top Processes',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.tune_rounded),
            label: 'Controls',
          ),
        ],
      ),
    );
  }
}

// ── Top Bar ──────────────────────────────────────────────────────────────────
class _TopBar extends StatelessWidget {
  final String host;
  final bool isConnected;
  final VoidCallback onDisconnect;

  const _TopBar(
      {required this.host,
      required this.isConnected,
      required this.onDisconnect});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.07))),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF00B4D8), Color(0xFF7C4DFF)],
              ),
              borderRadius: BorderRadius.circular(10),
            ),
            child:
                const Icon(Icons.monitor_heart_rounded, color: Colors.white, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'SRMP Monitor',
                  style: GoogleFonts.inter(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Row(
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: isConnected
                            ? const Color(0xFF00E676)
                            : const Color(0xFFFF1744),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      isConnected ? host : 'Disconnected',
                      style: const TextStyle(color: Colors.white38, fontSize: 11),
                    ),
                  ],
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.power_settings_new_rounded,
                color: Colors.white38, size: 20),
            onPressed: onDisconnect,
            tooltip: 'Disconnect',
          ),
        ],
      ),
    );
  }
}

// ── Left Panel ───────────────────────────────────────────────────────────────
class _LeftPanel extends StatelessWidget {
  final dynamic metric;
  final MonitorProvider monitor;

  const _LeftPanel({required this.metric, required this.monitor});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Gauges
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              GaugeWidget(
                value: metric?.cpu ?? 0,
                label: 'CPU',
                size: 110,
              ),
              GaugeWidget(
                value: metric?.ram ?? 0,
                label: 'RAM',
                size: 110,
              ),
              GaugeWidget(
                value: metric?.disk ?? 0,
                label: 'Disk',
                size: 110,
              ),
            ],
          ),
          const SizedBox(height: 16),

          // ── Temperature Cards (CPU & GPU) ──────────────────────────
          Row(
            children: [
              Expanded(
                child: _StatCard(
                  icon: Icons.thermostat_rounded,
                  label: 'CPU Temp',
                  value: metric != null
                      ? (metric.tempCpu > 0
                          ? '${metric.tempCpu.toStringAsFixed(0)}°C'
                          : 'Req Admin')
                      : '—',
                  subValue: metric != null && metric.tempCpu == 0
                      ? 'Run as Admin'
                      : null,
                  color: metric != null && metric.tempCpu > 80
                      ? const Color(0xFFFF1744)
                      : (metric != null && metric.tempCpu > 0
                          ? const Color(0xFFFF6D00)
                          : const Color(0xFF9E9E9E)),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _StatCard(
                  icon: Icons.developer_board_rounded,
                  label: 'GPU Temp',
                  value: metric != null
                      ? (metric.tempGpu > 0
                          ? '${metric.tempGpu.toStringAsFixed(0)}°C'
                          : '—')
                      : '—',
                  subValue: metric != null && metric.tempGpu > 0
                      ? 'RTX 4060'
                      : null,
                  color: metric != null && metric.tempGpu > 80
                      ? const Color(0xFFFF1744)
                      : const Color(0xFF00E676),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // ── Ping Cards (Server & Client) ───────────────────────────────
          Row(
            children: [
              Expanded(
                child: _StatCard(
                  icon: metric != null && metric.netOnline
                      ? Icons.public_rounded
                      : Icons.public_off_rounded,
                  label: 'Server Ping',
                  value: metric != null
                      ? (metric.netOnline
                          ? (metric.netPing > 0
                              ? '${metric.netPing}ms'
                              : '<1ms')
                          : 'Offline')
                      : '—',
                  subValue: 'Server → 8.8.8.8',
                  color: metric != null && metric.netOnline
                      ? (metric.netPing > 100
                          ? const Color(0xFFFF6D00)
                          : const Color(0xFF00E676))
                      : const Color(0xFFFF1744),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _StatCard(
                  icon: Icons.router_rounded,
                  label: 'Client Ping',
                  value: monitor.clientPingMs >= 0
                      ? '${monitor.clientPingMs}ms'
                      : '—',
                  subValue: 'You → 8.8.8.8',
                  color: monitor.clientPingMs < 0
                      ? const Color(0xFF9E9E9E)
                      : (monitor.clientPingMs > 100
                          ? const Color(0xFFFF6D00)
                          : const Color(0xFF00B4D8)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // ── Network Speed ───────────────────────────────────────────
          Row(
            children: [
              Expanded(
                child: _StatCard(
                  icon: Icons.upload_rounded,
                  label: 'Upload',
                  value: metric != null
                      ? '${metric.netUp.toStringAsFixed(2)} MB/s'
                      : '—',
                  color: const Color(0xFF00E676),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _StatCard(
                  icon: Icons.download_rounded,
                  label: 'Download',
                  value: metric != null
                      ? '${metric.netDown.toStringAsFixed(2)} MB/s'
                      : '—',
                  color: const Color(0xFF00B4D8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // ── Uptime ──────────────────────────────────────────────────
          _StatCard(
            icon: Icons.access_time_rounded,
            label: 'System Uptime',
            value: metric?.uptimeFormatted ?? '—',
            color: const Color(0xFF7C4DFF),
          ),

          const SizedBox(height: 16),

          // Event Log
          _EventLog(events: monitor.eventLog),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final String? subValue;
  final Color color;

  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    this.subValue,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(label,
                    style: const TextStyle(
                        color: Colors.white38, fontSize: 10)),
                const SizedBox(height: 1),
                Text(value,
                    style: TextStyle(
                        color: color,
                        fontSize: 13,
                        fontWeight: FontWeight.w700)),
                if (subValue != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    subValue!,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.4),
                      fontSize: 9,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _EventLog extends StatelessWidget {
  final List<String> events;
  const _EventLog({required this.events});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 160,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'EVENT LOG',
            style: TextStyle(
              color: Colors.white38,
              fontSize: 10,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(height: 6),
          Expanded(
            child: events.isEmpty
                ? const Center(
                    child: Text('No events yet',
                        style: TextStyle(color: Colors.white24, fontSize: 11)))
                : ListView.builder(
                    reverse: false,
                    itemCount: events.length,
                    itemBuilder: (_, i) => Text(
                      events[i],
                      style: GoogleFonts.robotoMono(
                          color: Colors.white54, fontSize: 10),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Process Panel ─────────────────────────────────────────────────────────────
class _ProcessPanel extends StatelessWidget {
  final MonitorProvider monitor;
  final String sortby;
  final ValueChanged<String> onSortChange;

  const _ProcessPanel({
    required this.monitor,
    required this.sortby,
    required this.onSortChange,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Header
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            children: [
              const Icon(Icons.list_alt_rounded,
                  color: Color(0xFF00B4D8), size: 18),
              const SizedBox(width: 8),
              Text(
                'Top Processes',
                style: GoogleFonts.inter(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(width: 8),
              _LiveBadge(),   // 🔴 LIVE indicator
              const Spacer(),

              // Sort toggle
              _SortToggle(current: sortby, onChanged: onSortChange),

              const SizedBox(width: 8),

              // Refresh button
              IconButton(
                icon: monitor.isLoadingProcs
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Color(0xFF00B4D8)))
                    : const Icon(Icons.refresh_rounded,
                        color: Color(0xFF00B4D8), size: 20),
                onPressed: () => monitor.refreshProcesses(sortby: sortby),
              ),
            ],
          ),
        ),

        // List
        Expanded(
          child: monitor.processes.isEmpty
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.hourglass_empty_rounded,
                          color: Colors.white24, size: 36),
                      const SizedBox(height: 8),
                      Text('Loading processes...',
                          style: const TextStyle(
                              color: Colors.white24, fontSize: 12)),
                    ],
                  ),
                )
              : ListView.builder(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  itemCount: monitor.processes.length,
                  itemBuilder: (_, i) {
                    final proc = monitor.processes[i];
                    return ProcessTile(
                      process: proc,
                      onKill: () {
                        showDialog(
                          context: context,
                          builder: (_) => _KillConfirmDialog(
                            processName: proc.name,
                            pid: proc.pid,
                            onConfirm: () => monitor.killProcess(proc.pid, proc.name),
                          ),
                        );
                      },
                    );
                  },
                ),
        ),

        // Kill result toast
        if (monitor.lastKillResult != null)
          _KillResultBar(message: monitor.lastKillResult!),
      ],
    );
  }
}

class _SortToggle extends StatelessWidget {
  final String current;
  final ValueChanged<String> onChanged;

  const _SortToggle({
    required this.current,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: ['CPU', 'RAM'].map((s) {
          final active = s == current;
          return GestureDetector(
            onTap: () {
              if (current != s) {
                onChanged(s);
              }
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: active
                    ? const Color(0xFF00B4D8).withOpacity(0.2)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(7),
              ),
              child: Text(
                s,
                style: TextStyle(
                  color: active
                      ? const Color(0xFF00B4D8)
                      : Colors.white38,
                  fontSize: 12,
                  fontWeight: active ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _KillConfirmDialog extends StatelessWidget {
  final String processName;
  final int pid;
  final VoidCallback onConfirm;

  const _KillConfirmDialog({
    required this.processName,
    required this.pid,
    required this.onConfirm,
  });

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: const Color(0xFF141828),
      shape:
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      title: const Row(
        children: [
          Icon(Icons.warning_amber_rounded,
              color: Color(0xFFFF6D00), size: 22),
          SizedBox(width: 8),
          Text('Kill Process',
              style: TextStyle(color: Colors.white, fontSize: 18)),
        ],
      ),
      content: Text(
        'Terminate "$processName" (PID $pid)?\n\nThis will send KILL_PROC to the server.',
        style: const TextStyle(color: Colors.white70, fontSize: 13),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel',
              style: TextStyle(color: Colors.white38)),
        ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFFFF1744),
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
          onPressed: () {
            Navigator.pop(context);
            onConfirm();
          },
          child: const Text('Kill Task',
              style: TextStyle(
                  color: Colors.white, fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }
}

class _KillResultBar extends StatelessWidget {
  final String message;
  const _KillResultBar({required this.message});

  @override
  Widget build(BuildContext context) {
    final isOk = message.startsWith('✅');
    final color =
        isOk ? const Color(0xFF00E676) : const Color(0xFFFF1744);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: color.withOpacity(0.1),
      child: Text(
        message,
        style: TextStyle(
            color: color, fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// Pulsing LIVE badge — shows real-time auto-refresh is active (2s interval)
class _LiveBadge extends StatefulWidget {
  const _LiveBadge();

  @override
  State<_LiveBadge> createState() => _LiveBadgeState();
}

class _LiveBadgeState extends State<_LiveBadge>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 900),
        reverseDuration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
    _opacity = Tween<double>(begin: 0.3, end: 1.0)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _opacity,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
        decoration: BoxDecoration(
          color: const Color(0xFFFF1744).withOpacity(0.15),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
              color: const Color(0xFFFF1744).withOpacity(0.5), width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 5,
              height: 5,
              decoration: const BoxDecoration(
                color: Color(0xFFFF1744),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 4),
            const Text(
              'LIVE',
              style: TextStyle(
                color: Color(0xFFFF1744),
                fontSize: 9,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.8,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Control Panel ─────────────────────────────────────────────────────────────
class _ControlPanel extends StatefulWidget {
  final MonitorProvider monitor;
  const _ControlPanel({required this.monitor});

  @override
  State<_ControlPanel> createState() => _ControlPanelState();
}

class _ControlPanelState extends State<_ControlPanel> {
  double? _localVolume;       // local state while dragging
  double? _localBrightness;  // local state while dragging

  @override
  Widget build(BuildContext context) {
    final monitor = widget.monitor;
    final vol = _localVolume ?? (monitor.currentVolume >= 0 ? monitor.currentVolume.toDouble() : 50.0);
    final bright = _localBrightness ?? (monitor.currentBrightness >= 0 ? monitor.currentBrightness.toDouble() : 50.0);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ──────────────────────────────────────────────────────
          Row(children: [
            const Icon(Icons.tune_rounded, color: Color(0xFF00B4D8), size: 18),
            const SizedBox(width: 8),
            Text('Remote Controls', style: GoogleFonts.inter(
              color: Colors.white, fontSize: 15, fontWeight: FontWeight.w700)),
          ]),

          // ── Result Banner ────────────────────────────────────────────────
          if (monitor.controlResult != null) ...[
            const SizedBox(height: 12),
            GestureDetector(
              onTap: () => monitor.clearControlResult(),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: monitor.controlResult!.startsWith('✅')
                      ? const Color(0xFF00E676).withOpacity(0.12)
                      : const Color(0xFFFF1744).withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: monitor.controlResult!.startsWith('✅')
                        ? const Color(0xFF00E676).withOpacity(0.4)
                        : const Color(0xFFFF1744).withOpacity(0.4),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      monitor.controlResult!.startsWith('✅')
                          ? Icons.check_circle_outline_rounded
                          : Icons.error_outline_rounded,
                      color: monitor.controlResult!.startsWith('✅')
                          ? const Color(0xFF00E676)
                          : const Color(0xFFFF1744),
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        monitor.controlResult!,
                        style: TextStyle(
                          color: monitor.controlResult!.startsWith('✅')
                              ? const Color(0xFF00E676)
                              : const Color(0xFFFF1744),
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    Icon(Icons.close_rounded,
                        color: Colors.white24, size: 14),
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 20),

          // ── Volume ───────────────────────────────────────────────────────
          _SectionHeader(icon: Icons.volume_up_rounded, label: 'System Volume',
              value: monitor.currentVolume >= 0 ? '${vol.round()}%' : '—',
              color: const Color(0xFF00E676)),
          const SizedBox(height: 8),
          _SliderCard(
            value: vol,
            color: const Color(0xFF00E676),
            min: 0, max: 100,
            onChanged: (v) => setState(() => _localVolume = v),
            onChangeEnd: (v) {
              setState(() => _localVolume = null);
              monitor.setVolume(v.round());
            },
          ),
          const SizedBox(height: 20),

          // ── Brightness ───────────────────────────────────────────────────
          _SectionHeader(icon: Icons.brightness_6_rounded, label: 'Screen Brightness',
              value: monitor.currentBrightness >= 0 ? '${bright.round()}%' : 'N/A',
              color: const Color(0xFFFFD600)),
          const SizedBox(height: 8),
          _SliderCard(
            value: bright,
            color: const Color(0xFFFFD600),
            min: 0, max: 100,
            onChanged: (v) => setState(() => _localBrightness = v),
            onChangeEnd: (v) {
              setState(() => _localBrightness = null);
              monitor.setBrightness(v.round());
            },
          ),
          const SizedBox(height: 24),

          // ── Power Control ────────────────────────────────────────────────
          Row(children: [
            const Icon(Icons.power_settings_new_rounded, color: Color(0xFFFF6D00), size: 18),
            const SizedBox(width: 8),
            Text('Power Control', style: GoogleFonts.inter(
              color: Colors.white, fontSize: 15, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 12),

          // Lock
          _PowerButton(
            icon: Icons.lock_rounded,
            label: 'Lock Screen',
            subtitle: 'Lock the PC immediately',
            color: const Color(0xFF00B4D8),
            onTap: () => monitor.sysPower('LOCK'),
          ),
          const SizedBox(height: 8),

          // Restart
          _PowerButton(
            icon: Icons.refresh_rounded,
            label: 'Restart',
            subtitle: 'Restart PC in 5 seconds',
            color: const Color(0xFFFF6D00),
            onTap: () => _confirmPower(context, 'RESTART', 'Restart', monitor),
          ),
          const SizedBox(height: 8),

          // Shutdown
          _PowerButton(
            icon: Icons.power_off_rounded,
            label: 'Shutdown',
            subtitle: 'Shut down PC in 5 seconds',
            color: const Color(0xFFFF1744),
            onTap: () => _confirmPower(context, 'SHUTDOWN', 'Shutdown', monitor),
          ),
        ],
      ),
    );
  }

  void _confirmPower(BuildContext ctx, String action, String label, MonitorProvider monitor) {
    showDialog(
      context: ctx,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF141828),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(children: [
          Icon(
            action == 'SHUTDOWN' ? Icons.power_off_rounded : Icons.refresh_rounded,
            color: action == 'SHUTDOWN' ? const Color(0xFFFF1744) : const Color(0xFFFF6D00),
            size: 22,
          ),
          const SizedBox(width: 8),
          Text('Confirm $label',
              style: const TextStyle(color: Colors.white, fontSize: 18)),
        ]),
        content: Text(
          '$label the server PC in 5 seconds?',
          style: const TextStyle(color: Colors.white70, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: Colors.white38)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: action == 'SHUTDOWN'
                  ? const Color(0xFFFF1744)
                  : const Color(0xFFFF6D00),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              monitor.sysPower(action);
            },
            child: Text(label,
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _SectionHeader({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: color, size: 16),
        const SizedBox(width: 8),
        Text(label, style: TextStyle(color: Colors.white70, fontSize: 13,
            fontWeight: FontWeight.w600)),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withOpacity(0.15),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withOpacity(0.3)),
          ),
          child: Text(value, style: TextStyle(
              color: color, fontSize: 12, fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }
}

class _SliderCard extends StatelessWidget {
  final double value;
  final double min;
  final double max;
  final Color color;
  final ValueChanged<double> onChanged;
  final ValueChanged<double> onChangeEnd;

  const _SliderCard({
    required this.value,
    required this.min,
    required this.max,
    required this.color,
    required this.onChanged,
    required this.onChangeEnd,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.06),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: SliderTheme(
        data: SliderTheme.of(context).copyWith(
          activeTrackColor: color,
          inactiveTrackColor: color.withOpacity(0.15),
          thumbColor: color,
          overlayColor: color.withOpacity(0.2),
          thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
          trackHeight: 4,
        ),
        child: Slider(
          value: value.clamp(min, max),
          min: min,
          max: max,
          onChanged: onChanged,
          onChangeEnd: onChangeEnd,
        ),
      ),
    );
  }
}

class _PowerButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;

  const _PowerButton({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: color.withOpacity(0.07),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: color.withOpacity(0.25)),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: TextStyle(
                        color: color, fontSize: 14, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text(subtitle, style: const TextStyle(
                        color: Colors.white38, fontSize: 11)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: color.withOpacity(0.5)),
            ],
          ),
        ),
      ),
    );
  }
}
