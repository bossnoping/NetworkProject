import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'providers/monitor_provider.dart';
import 'screens/connect_screen.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => MonitorProvider(),
      child: const SRMPApp(),
    ),
  );
}

class SRMPApp extends StatelessWidget {
  const SRMPApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SRMP Monitor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00B4D8),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        textTheme: GoogleFonts.interTextTheme(
          ThemeData.dark().textTheme,
        ),
        scaffoldBackgroundColor: const Color(0xFF0A0E1A),
      ),
      home: const ConnectScreen(),
    );
  }
}
