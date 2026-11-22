import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;

/// Data model representing EFSA & AI-evaluated Food Safety & Additives analysis (LabelLens).
class FoodSafetyAnalysisResult {
  final int healthScore;
  final int kidsScore;
  final String summary;
  final String? kidsVerdict;
  final NutritionData? nutrition;
  final List<HarmfulAdditiveItem> harmfulAdditives;
  final List<PreservativeItem> preservatives;
  final List<IngredientItem> ingredients;
  final int? novaGroup;
  final List<String> overallConcerns;
  final List<String> goodPoints;

  const FoodSafetyAnalysisResult({
    required this.healthScore,
    required this.kidsScore,
    required this.summary,
    this.kidsVerdict,
    this.nutrition,
    this.harmfulAdditives = const [],
    this.preservatives = const [],
    this.ingredients = const [],
    this.novaGroup,
    this.overallConcerns = const [],
    this.goodPoints = const [],
  });

  factory FoodSafetyAnalysisResult.fromJson(Map<String, dynamic> json) {
    return FoodSafetyAnalysisResult(
      healthScore: (json['health_score'] as num?)?.toInt() ?? 50,
      kidsScore: (json['kids_score'] as num?)?.toInt() ?? 50,
      summary: json['summary'] as String? ?? 'Analysis completed.',
      kidsVerdict: json['kids_verdict'] as String?,
      nutrition: json['nutrition_per_100g'] != null && json['nutrition_per_100g'] is Map<String, dynamic>
          ? NutritionData.fromJson(json['nutrition_per_100g'] as Map<String, dynamic>)
          : null,
      harmfulAdditives: ((json['harmful_additives'] as List<dynamic>?) ?? [])
          .map((e) => HarmfulAdditiveItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      preservatives: ((json['preservatives'] as List<dynamic>?) ?? [])
          .map((e) => PreservativeItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      ingredients: ((json['ingredients'] as List<dynamic>?) ?? [])
          .map((e) => IngredientItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      novaGroup: (json['nova_group'] as num?)?.toInt(),
      overallConcerns: ((json['overall_concerns'] as List<dynamic>?) ?? [])
          .map((e) => e.toString())
          .toList(),
      goodPoints: ((json['good_points'] as List<dynamic>?) ?? [])
          .map((e) => e.toString())
          .toList(),
    );
  }
}

class NutritionData {
  final double? energyKcal;
  final double? fatG;
  final double? saturatedFatG;
  final double? carbohydratesG;
  final double? sugarsG;
  final double? proteinG;
  final double? saltG;
  final double? sodiumMg;
  final double? fibreG;

  const NutritionData({
    this.energyKcal,
    this.fatG,
    this.saturatedFatG,
    this.carbohydratesG,
    this.sugarsG,
    this.proteinG,
    this.saltG,
    this.sodiumMg,
    this.fibreG,
  });

  factory NutritionData.fromJson(Map<String, dynamic> json) {
    double? parseD(dynamic v) => v == null ? null : (v as num).toDouble();
    return NutritionData(
      energyKcal: parseD(json['energy_kcal']),
      fatG: parseD(json['fat_g']),
      saturatedFatG: parseD(json['saturated_fat_g']),
      carbohydratesG: parseD(json['carbohydrates_g']),
      sugarsG: parseD(json['sugars_g']),
      proteinG: parseD(json['protein_g']),
      saltG: parseD(json['salt_g']),
      sodiumMg: parseD(json['sodium_mg']),
      fibreG: parseD(json['fibre_g']),
    );
  }
}

class HarmfulAdditiveItem {
  final String name;
  final String? eNumber;
  final String whyHarmful;
  final String safeLimitPerDay;
  final bool kidsConcern;
  final String? kidsNote;

  const HarmfulAdditiveItem({
    required this.name,
    this.eNumber,
    required this.whyHarmful,
    required this.safeLimitPerDay,
    this.kidsConcern = false,
    this.kidsNote,
  });

  factory HarmfulAdditiveItem.fromJson(Map<String, dynamic> json) {
    return HarmfulAdditiveItem(
      name: json['name'] as String? ?? 'Additive',
      eNumber: json['e_number'] as String?,
      whyHarmful: json['why_harmful'] as String? ?? '',
      safeLimitPerDay: json['safe_limit_per_day'] as String? ?? 'Not established',
      kidsConcern: (json['kids_concern'] as bool?) ?? false,
      kidsNote: json['kids_note'] as String?,
    );
  }
}

class PreservativeItem {
  final String name;
  final String? eNumber;
  final String concernLevel;
  final String note;
  final String? safeLimitPerDay;

  const PreservativeItem({
    required this.name,
    this.eNumber,
    required this.concernLevel,
    required this.note,
    this.safeLimitPerDay,
  });

  factory PreservativeItem.fromJson(Map<String, dynamic> json) {
    return PreservativeItem(
      name: json['name'] as String? ?? 'Preservative',
      eNumber: json['e_number'] as String?,
      concernLevel: json['concern_level'] as String? ?? 'safe',
      note: json['note'] as String? ?? '',
      safeLimitPerDay: json['safe_limit_per_day'] as String?,
    );
  }
}

class IngredientItem {
  final String name;
  final String category;
  final String safeLimit;
  final String concernLevel;
  final bool kidsSafe;
  final String? note;

  const IngredientItem({
    required this.name,
    required this.category,
    required this.safeLimit,
    required this.concernLevel,
    this.kidsSafe = true,
    this.note,
  });

  factory IngredientItem.fromJson(Map<String, dynamic> json) {
    return IngredientItem(
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? 'Base ingredient',
      safeLimit: json['safe_limit'] as String? ?? 'No established limit',
      concernLevel: json['concern_level'] as String? ?? 'safe',
      kidsSafe: (json['kids_safe'] as bool?) ?? true,
      note: json['note'] as String?,
    );
  }
}

/// Client service communicating with Veriqoo's Food Safety & Additives endpoints.
class FoodSafetyApiService {
  final String baseUrl;
  final http.Client _httpClient;

  FoodSafetyApiService({
    String? baseUrl,
    http.Client? httpClient,
  })  : baseUrl = baseUrl ??
            const String.fromEnvironment(
              'VERIQOO_API_URL',
              defaultValue: 'http://localhost:8000/api/v1',
            ),
        _httpClient = httpClient ?? http.Client();

  /// Analyse raw ingredients text declaration.
  Future<FoodSafetyAnalysisResult> analyseText(String ingredientsText, {String? productName}) async {
    final uri = Uri.parse('$baseUrl/food-safety/analyse-text');
    final response = await _httpClient.post(
      uri,
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: jsonEncode({
        'ingredients_text': ingredientsText,
        if (productName != null) 'product_name': productName,
      }),
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return FoodSafetyAnalysisResult.fromJson(data);
    } else {
      throw Exception('Food safety analysis failed (${response.statusCode}): ${response.body}');
    }
  }

  /// Analyse uploaded food label photograph.
  Future<FoodSafetyAnalysisResult> analyseImage(Uint8List imageBytes, {String filename = 'label.jpg'}) async {
    final uri = Uri.parse('$baseUrl/food-safety/analyse');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(http.MultipartFile.fromBytes('image', imageBytes, filename: filename));

    final streamed = await _httpClient.send(request);
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return FoodSafetyAnalysisResult.fromJson(data);
    } else {
      throw Exception('Food safety image analysis failed (${response.statusCode}): ${response.body}');
    }
  }
}
