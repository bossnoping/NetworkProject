import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:srmp_monitor/main.dart';
import 'package:srmp_monitor/providers/monitor_provider.dart';

void main() {
  testWidgets('SRMP app smoke test — connect screen renders', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => MonitorProvider(),
        child: const SRMPApp(),
      ),
    );
    // Connect screen should show the title
    expect(find.text('SRMP Monitor'), findsOneWidget);
    expect(find.text('Connect'), findsOneWidget);
  });
}
