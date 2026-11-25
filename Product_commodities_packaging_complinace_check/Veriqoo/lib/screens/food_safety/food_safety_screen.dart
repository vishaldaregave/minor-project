import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../services/food_safety_api_service.dart';

/// Screen for LabelLens: Food Safety, Additives, and EFSA Nutrition Analysis.
class FoodSafetyScreen extends StatefulWidget {
  const FoodSafetyScreen({super.key});

  @override
  State<FoodSafetyScreen> createState() => _FoodSafetyScreenState();
}

class _FoodSafetyScreenState extends State<FoodSafetyScreen> {
  final _apiService = FoodSafetyApiService();
  final _textController = TextEditingController();
  final _imagePicker = ImagePicker();
  final _textRecognizer = TextRecognizer();

  bool _isLoading = false;
  String? _errorMessage;
  FoodSafetyAnalysisResult? _result;
  Uint8List? _selectedImageBytes;

  @override
  void dispose() {
    _textController.dispose();
    _textRecognizer.close();
    super.dispose();
  }

  Future<void> _analyseText() async {
    final text = _textController.text.trim();
    if (text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter an ingredient list or snap a label photo.')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await _apiService.analyseText(text);
      setState(() {
        _result = res;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _pickAndAnalyseImage(ImageSource source) async {
    try {
      final picked = await _imagePicker.pickImage(source: source, maxWidth: 1600, imageQuality: 85);
      if (picked == null) return;

      final bytes = await picked.readAsBytes();
      setState(() {
        _selectedImageBytes = bytes;
        _isLoading = true;
        _errorMessage = null;
      });

      // Extract label text using on-device ML Kit OCR
      String ocrText = '';
      try {
        final inputImage = InputImage.fromFilePath(picked.path);
        final recognized = await _textRecognizer.processImage(inputImage);
        ocrText = recognized.text.trim();
        if (ocrText.isNotEmpty) {
          _textController.text = ocrText;
        }
      } catch (ocrErr) {
        debugPrint('On-device OCR error: $ocrErr');
      }

      final res = await _apiService.analyseImage(
        bytes,
        filename: picked.name,
        extractedOcrText: ocrText,
      );
      setState(() {
        _result = res;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Color _getScoreColor(int score) {
    if (score >= 75) return const Color(0xFF00C896);
    if (score >= 50) return const Color(0xFFFFB800);
    return const Color(0xFFFF4D4D);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F3),
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.biotech_rounded, color: Color(0xFF183B32), size: 24),
            SizedBox(width: 8),
            Text(
              'LabelLens • Food Safety',
              style: TextStyle(
                color: Color(0xFF17201D),
                fontWeight: FontWeight.bold,
                fontSize: 18,
              ),
            ),
          ],
        ),
        backgroundColor: const Color(0xFFF7F7F3),
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header Card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFF183B32),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'AI Food Label & EFSA Additive Lens',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    SizedBox(height: 6),
                    Text(
                      'Cross-reference ingredients against 3,175+ EFSA OpenFoodTox substances, detect harmful additives, and evaluate child safety.',
                      style: TextStyle(color: Color(0xFFB5C9C3), fontSize: 13, height: 1.4),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // Input Actions Card
              Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: const BorderSide(color: Color(0xFFE2E4DE)),
                ),
                color: Colors.white,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text(
                        'Ingredient List or Label Photo',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF17201D)),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _textController,
                        maxLines: 3,
                        decoration: InputDecoration(
                          hintText: 'e.g. Sugar, Vegetable oil, Tartrazine (E102), Sodium benzoate (E211), Citric acid...',
                          hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 13),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                          filled: true,
                          fillColor: const Color(0xFFF9FAF8),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: SizedBox(
                              height: 48,
                              child: OutlinedButton.icon(
                                onPressed: _isLoading ? null : () => _pickAndAnalyseImage(ImageSource.camera),
                                icon: const Icon(Icons.camera_alt_rounded, size: 18),
                                label: const Text('Take Photo', style: TextStyle(fontWeight: FontWeight.w600)),
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: const Color(0xFF183B32),
                                  side: const BorderSide(color: Color(0xFF183B32), width: 1.2),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: SizedBox(
                              height: 48,
                              child: OutlinedButton.icon(
                                onPressed: _isLoading ? null : () => _pickAndAnalyseImage(ImageSource.gallery),
                                icon: const Icon(Icons.photo_library_outlined, size: 18),
                                label: const Text('Upload Photo', style: TextStyle(fontWeight: FontWeight.w600)),
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: const Color(0xFF183B32),
                                  side: const BorderSide(color: Color(0xFF183B32), width: 1.2),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      SizedBox(
                        width: double.infinity,
                        height: 48,
                        child: ElevatedButton.icon(
                          onPressed: _isLoading ? null : _analyseText,
                          icon: _isLoading
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                )
                              : const Icon(Icons.biotech_rounded, size: 20),
                          label: Text(
                            _isLoading ? 'Analyzing Food Safety...' : 'Analyse Ingredients & EFSA Additives',
                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF183B32),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              if (_selectedImageBytes != null) ...[
                const SizedBox(height: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.memory(_selectedImageBytes!, height: 160, fit: BoxFit.cover),
                ),
              ],

              if (_isLoading) ...[
                const SizedBox(height: 32),
                const Center(
                  child: Column(
                    children: [
                      CircularProgressIndicator(color: Color(0xFF183B32)),
                      SizedBox(height: 12),
                      Text('Running EFSA toxicology search & safety audit...', style: TextStyle(color: Color(0xFF68716D))),
                    ],
                  ),
                ),
              ],

              if (_errorMessage != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFEEEE),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: Colors.red.shade200),
                  ),
                  child: Text(_errorMessage!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                ),
              ],

              if (_result != null && !_isLoading) ...[
                const SizedBox(height: 20),
                _buildResultsView(_result!),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResultsView(FoodSafetyAnalysisResult res) {
    final scoreColor = _getScoreColor(res.healthScore);
    final kidsScoreColor = _getScoreColor(res.kidsScore);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Score Indicators
        Row(
          children: [
            Expanded(
              child: Card(
                elevation: 0,
                color: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: Color(0xFFE2E4DE))),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Text(
                        '${res.healthScore}',
                        style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold, color: scoreColor),
                      ),
                      const Text('Overall Health Score', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF68716D))),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Card(
                elevation: 0,
                color: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: Color(0xFFE2E4DE))),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Text(
                        '${res.kidsScore}',
                        style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold, color: kidsScoreColor),
                      ),
                      const Text('Kids Safety Score', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF68716D))),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),

        const SizedBox(height: 12),

        // Summary Card
        Card(
          elevation: 0,
          color: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: Color(0xFFE2E4DE))),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.assignment_outlined, size: 20, color: Color(0xFF183B32)),
                    SizedBox(width: 8),
                    Text('Plain-English Verdict', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 8),
                Text(res.summary, style: const TextStyle(fontSize: 14, height: 1.4, color: Color(0xFF17201D))),
                if (res.kidsVerdict != null) ...[
                  const Divider(height: 24),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.child_care_rounded, size: 20, color: Color(0xFFD97706)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Child Safety Verdict', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFFD97706))),
                            const SizedBox(height: 2),
                            Text(res.kidsVerdict!, style: const TextStyle(fontSize: 13, color: Color(0xFF17201D))),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),

        // Harmful Additives Card
        if (res.harmfulAdditives.isNotEmpty) ...[
          const SizedBox(height: 12),
          Card(
            elevation: 0,
            color: const Color(0xFFFFF5F5),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: Color(0xFFFFD1D1))),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded, color: Color(0xFFFF4D4D)),
                      const SizedBox(width: 8),
                      Text(
                        'Harmful Additives Flagged (${res.harmfulAdditives.length})',
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Color(0xFFCC0000)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  ...res.harmfulAdditives.map((item) => Padding(
                        padding: const EdgeInsets.only(bottom: 8.0),
                        child: Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8)),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(item.name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                                  if (item.eNumber != null) ...[
                                    const SizedBox(width: 6),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                      decoration: BoxDecoration(color: Colors.red.shade100, borderRadius: BorderRadius.circular(4)),
                                      child: Text(item.eNumber!, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.red)),
                                    ),
                                  ],
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(item.whyHarmful, style: const TextStyle(fontSize: 12, color: Color(0xFF4A4A4A))),
                              const SizedBox(height: 4),
                              Text('Safe Limit: ${item.safeLimitPerDay}', style: TextStyle(fontSize: 11, color: Colors.grey.shade600, fontStyle: FontStyle.italic)),
                            ],
                          ),
                        ),
                      )),
                ],
              ),
            ),
          ),
        ],

        // Ingredients Breakdown
        if (res.ingredients.isNotEmpty) ...[
          const SizedBox(height: 12),
          Card(
            elevation: 0,
            color: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: Color(0xFFE2E4DE))),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Ingredient Classification', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: res.ingredients.map((ing) {
                      Color bg = const Color(0xFFF0FDF4);
                      Color textC = const Color(0xFF166534);
                      if (ing.concernLevel == 'moderate') {
                        bg = const Color(0xFFFFFBEB);
                        textC = const Color(0xFFB45309);
                      } else if (ing.concernLevel == 'harmful') {
                        bg = const Color(0xFFFEF2F2);
                        textC = const Color(0xFF991B1B);
                      }
                      return Chip(
                        label: Text('${ing.name} (${ing.category})', style: TextStyle(fontSize: 11, color: textC)),
                        backgroundColor: bg,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        side: BorderSide(color: textC.withValues(alpha: 0.3)),
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}
