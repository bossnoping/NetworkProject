import 'package:flutter/material.dart';
import '../models/process_info.dart';

/// ProcessTile — displays a process row with CPU/RAM bars and a Kill button.
class ProcessTile extends StatelessWidget {
  final ProcessInfo process;
  final VoidCallback onKill;

  const ProcessTile({
    super.key,
    required this.process,
    required this.onKill,
  });

  Color _cpuColor(double v) {
    if (v < 20) return const Color(0xFF00E676);
    if (v < 50) return const Color(0xFFFFD600);
    if (v < 80) return const Color(0xFFFF6D00);
    return const Color(0xFFFF1744);
  }

  @override
  Widget build(BuildContext context) {
    final cpu = process.cpuPercent;
    final ram = process.ramPercent;
    final ramMb = process.ramMb;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 0),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(
          children: [
            // Process icon
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: _cpuColor(cpu).withOpacity(0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                Icons.memory_rounded,
                color: _cpuColor(cpu),
                size: 20,
              ),
            ),
            const SizedBox(width: 12),

            // Name + bars
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          process.name,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Text(
                        'PID ${process.pid}',
                        style: TextStyle(
                          color: Colors.white38,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  // CPU bar
                  _MiniBar(
                    label: 'CPU',
                    value: cpu / 100,
                    valueText: '${cpu.toStringAsFixed(1)}%',
                    color: _cpuColor(cpu),
                  ),
                  const SizedBox(height: 3),
                  // RAM bar
                  _MiniBar(
                    label: 'RAM',
                    value: ram / 100,
                    valueText: '${ramMb.toStringAsFixed(1)} MB',
                    color: const Color(0xFF7C4DFF),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),

            // Kill button
            _KillButton(onTap: onKill),
          ],
        ),
      ),
    );
  }
}

class _MiniBar extends StatelessWidget {
  final String label;
  final double value;
  final String valueText;
  final Color color;

  const _MiniBar({
    required this.label,
    required this.value,
    required this.valueText,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 28,
          child: Text(
            label,
            style: TextStyle(color: Colors.white38, fontSize: 10),
          ),
        ),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: value.clamp(0.0, 1.0),
              backgroundColor: Colors.white.withOpacity(0.07),
              valueColor: AlwaysStoppedAnimation(color),
              minHeight: 5,
            ),
          ),
        ),
        const SizedBox(width: 6),
        SizedBox(
          width: 38,
          child: Text(
            valueText,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.w600,
            ),
            textAlign: TextAlign.right,
          ),
        ),
      ],
    );
  }
}

class _KillButton extends StatefulWidget {
  final VoidCallback onTap;
  const _KillButton({required this.onTap});

  @override
  State<_KillButton> createState() => _KillButtonState();
}

class _KillButtonState extends State<_KillButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onTap();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: _pressed
              ? const Color(0xFFFF1744).withOpacity(0.3)
              : const Color(0xFFFF1744).withOpacity(0.12),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: const Color(0xFFFF1744).withOpacity(_pressed ? 0.8 : 0.4),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.close_rounded, size: 14, color: Color(0xFFFF1744)),
            SizedBox(width: 4),
            Text(
              'Kill',
              style: TextStyle(
                color: Color(0xFFFF1744),
                fontSize: 11,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
