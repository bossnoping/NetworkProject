import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Circular gauge widget with animated fill, color zones, and center label.
class GaugeWidget extends StatefulWidget {
  final double value;       // 0.0 – 100.0
  final String label;       // e.g. 'CPU'
  final String unit;        // e.g. '%'
  final double size;

  const GaugeWidget({
    super.key,
    required this.value,
    required this.label,
    this.unit = '%',
    this.size = 160,
  });

  @override
  State<GaugeWidget> createState() => _GaugeWidgetState();
}

class _GaugeWidgetState extends State<GaugeWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;
  double _prevValue = 0;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _anim = Tween<double>(begin: 0, end: widget.value)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
    _ctrl.forward();
    _prevValue = widget.value;
  }

  @override
  void didUpdateWidget(GaugeWidget old) {
    super.didUpdateWidget(old);
    if ((widget.value - _prevValue).abs() > 0.1) {
      _anim = Tween<double>(begin: _prevValue, end: widget.value)
          .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
      _ctrl.forward(from: 0);
      _prevValue = widget.value;
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  /// Color based on value: green → yellow → orange → red
  Color _arcColor(double v) {
    if (v < 60) return const Color(0xFF00E676);
    if (v < 80) return const Color(0xFFFFD600);
    if (v < 90) return const Color(0xFFFF6D00);
    return const Color(0xFFFF1744);
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: AnimatedBuilder(
        animation: _anim,
        builder: (context, child) {
          final v = _anim.value.clamp(0.0, 100.0);
          return CustomPaint(
            painter: _GaugePainter(value: v, color: _arcColor(v)),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '${v.toStringAsFixed(1)}${widget.unit}',
                    style: TextStyle(
                      fontSize: widget.size * 0.175,
                      fontWeight: FontWeight.w700,
                      color: _arcColor(v),
                      letterSpacing: -0.5,
                    ),
                  ),
                  Text(
                    widget.label,
                    style: TextStyle(
                      fontSize: widget.size * 0.1,
                      color: Colors.white54,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  final double value;
  final Color color;

  _GaugePainter({required this.value, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 12;
    const startAngle = math.pi * 0.75;
    const sweepFull = math.pi * 1.5;
    final sweepFill = sweepFull * (value / 100.0);

    // Background track
    final trackPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..strokeCap = StrokeCap.round
      ..color = Colors.white.withOpacity(0.08);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepFull,
      false,
      trackPaint,
    );

    if (value <= 0) return;

    // Glow layer
    final glowPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 22
      ..strokeCap = StrokeCap.round
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8)
      ..color = color.withOpacity(0.25);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepFill,
      false,
      glowPaint,
    );

    // Fill arc
    final fillPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepFill,
      false,
      fillPaint,
    );
  }

  @override
  bool shouldRepaint(_GaugePainter old) =>
      old.value != value || old.color != color;
}
